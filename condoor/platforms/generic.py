# =============================================================================
# generic.py
#
# Copyright (c)  2016, Cisco Systems
# All rights reserved.
#
# # Author: Klaudiusz Staniek
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
# Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
# THE POSSIBILITY OF SUCH DAMAGE.
# =============================================================================


import re
import pexpect
from threading import Lock

from ..exceptions import \
    ConnectionError,\
    CommandSyntaxError, \
    CommandTimeoutError

from ..controllers.fsm import FSM, action

from ..controllers.protocols.base import PRESS_RETURN

_PROMPT_IOSXR = re.compile('\w+/\w+/\w+/\w+:.+#')
_PROMPT_SHELL = re.compile('\$\s*|>\s*')

_PROMPT_XML = 'XML> '
_INVALID_INPUT = "Invalid input detected"
_INCOMPLETE_COMMAND = "Incomplete command."
_CONNECTION_CLOSED = "Connection closed"

prompt_patterns = {
    'IOSXR': re.compile('(RP/\d+/RS?P[0-1]/CPU[0-3]:.*?)(\([^()]*\))?#'),
    'CALVADOS': re.compile("sysadmin-vm:[0-3]_RS?P[0-1]#"),
    'ROMMON': re.compile("rommon [A|B]?\d+ >"),
    'IOS': re.compile('[\w\-]+[#|>]'),
    'NX-OS': re.compile('[\w\-]+# '),
}

os_types = ['IOSXR', 'CALVADOS', 'ROMMON', 'IOS', 'NX-OS']


class Connection(object):
    platform = 'generic'
    shell_prompt = "\$\s?|>\s?|#\s?|\%\s?"
    connection_closed_re = re.compile("Connection closed")
    rommon_prompt = re.compile("rommon.*>")
    # platform_prompt = re.compile('[\r\n][\r\n]((\w+/\w+/\w+/\w+:.*?)(\([^()]*\))?#|.*?[#|>])')
    platform_prompt = re.compile('[\w\-]+[#>]')

    password_prompt = re.compile("[P|p]assword:\s?")
    username_prompt = re.compile("([U|u]sername:\s|login:\s?)")

    command_syntax_re = re.compile('\% Bad IP address or host name% Unknown command or computer name, '
                                   'or unable to find computer address|'
                                   '\% Ambiguous command:.*"|"'
                                   '\% Type "show \?" for a list of subcommands'
                                   '\%(w+)?for a list of subcommands|'
                                   '\% Ambiguous command:|'
                                   '\% Invalid input detected|'
                                   "\% Invalid command at .* marker")  # NX-OS
    press_return = re.compile("Press RETURN to get started\.")
    more = re.compile(" --More-- ")
    standby_console = re.compile("Standby console disabled|\(standby\)")

    def __init__(self, name, hosts, controller_class, logger, account_manager=None):
        self.hosts = hosts
        self.account_manager = account_manager
        self.pending_connection = False
        self.connected = False
        self.command_execution_pending = Lock()
        self.ctrl = None
        self.ctrl_class = controller_class
        self.name = name
        self.hostname = name
        self.logger = logger
        self.prompt = self.platform_prompt
        self._os_type = 'unknown'
        self.mode = None
        self.compiled_prompts = []
        for _ in hosts:
            self.compiled_prompts.append(None)

    def __repr__(self):
        name = ""
        for host in self.hosts:
            name += "->{}".format(host)
        return name[2:]

    def connect(self, logfile=None):
        """
        Connection initialization method.
        If logfile is None then the common logfile from
        Args:
            logfile (fd): File description for session log

        Returns:
            True if connection is established successfully
            False on failure.
        """

        if not self.connected:
            self.ctrl = self.ctrl_class(self, self.hostname, self.hosts, self.account_manager, logfile=logfile)
            self._info("Connecting to {} using {} driver".format(self.__repr__(), self.platform))
            self.connected = self.ctrl.connect()

        if self.connected:
            self._info("Connected to {}".format(self.__repr__()))
            self._compile_prompts()
            self.prepare_prompt()
            self.prepare_terminal_session()
        else:
            raise ConnectionError("Connection failed", self.hostname)

        return self.connected

    def disconnect(self):
        """
        Tear down the connection

        Args:
            None

        Returns:
            None

        """
        self._info("Disconnecting from {}".format(self.__repr__()))
        self.ctrl.disconnect()
        self.connected = False
        self.pending_connection = False
        self._info("Disconnected")

    def reconnect(self, logfile=None):
        self.connect(logfile=logfile)

    @property
    def is_connected(self):
        if self.connected:
            return self.ctrl.connected
        else:
            return False

    def send(self, cmd="", timeout=60, wait_for_string=None):
        """
        Send the command to the device and return the output

        Args:
            cmd (str): Command string for execution. Defaults to empty string.
            timeout (int): Timeout in seconds. Defaults to 60s
            wait_for_string (str): This is optional string that driver
                waits for after command execution. If none the detected
                prompt will be used.

        Returns:
            A string containing the command output.

        Raises:
            ConnectionError: General connection error during command execution
            CommandSyntaxError: Command syntax error or unknown command.
            CommandTimeoutError: Timeout during command execution
        """
        if self.connected:
            self._debug("Sending command: '{}'".format(cmd))

            try:
                self._execute_command(cmd, timeout, wait_for_string)
            except ConnectionError:
                self._warning("Connection lost. Disconnecting.")
                self.disconnect()
                raise

            self._info("Command executed successfully: '{}'".format(cmd))
            output = self.ctrl.before
            # if output.startswith(cmd):
            #    remove first line which contains the command itself
            #    second_line_index = output.find('\n') + 1
            #    output = output[second_line_index:]
            output = output.replace('\r', '')
            return output

        else:
            raise ConnectionError("Device not connected", host=self.hostname)

    def send_xml(self, command):
        """
        Handle error i.e.
        ERROR: 0x24319600 'XML-TTY' detected the 'informational' condition
        'The XML TTY Agent has not yet been started.
        Check that the configuration 'xml agent tty' has been committed.'
        """
        self._debug("Starting XML TTY Agent")
        result = self.send("xml", wait_for_string=_PROMPT_XML)
        if result != '':
            return result
        self._info("XML TTY Agent started")

        result = self.send(command, wait_for_string=_PROMPT_XML)
        self.ctrl.sendcontrol('c')
        self.send()
        return result

    def netconf(self, command):
        """
        Handle error i.e.
        ERROR: 0x24319600 'XML-TTY' detected the 'informational' condition
        'The XML TTY Agent has not yet been started.
        Check that the configuration 'xml agent tty' has been committed.'
        """
        self._debug("Starting XML TTY Agent")
        result = self.send("netconf", wait_for_string=']]>]]>')
        # if result != '':
        #    return result
        self._info("XML TTY Agent started")

        self.ctrl.send(command)
        self.ctrl.send("\r\n")
        self.ctrl.expect("]]>]]>")
        result = self.ctrl.before
        self.ctrl.sendcontrol('c')
        self.send()
        return result

    def enable(self, enable_password=None):
        """This method changes the device mode to privileged. If device does not support privileged mode the
        the informational message to the log will be posted.

        Args:
            enable_password (str): The privileged mode password. This is optional parameter. If password is not
                provided but required the password from url will be used. Refer to :class:`condoor.Connection`
        """
        self._info("Ignoring. Not supported on this platform")

    def reload(self, rommon_boot_command="boot"):
        """This method reloads the device and waits for device to boot up. It post the informational message to the
        log if not implemented by device driver."""

        self._info("Ignoring. Not implemented for this platform")

    def run_fsm(self, name, command, events, transitions, timeout):
        """This method instantiate and run the Finite State Machine for the current device connection. Here is the
        example of usage::

            test_dir = "rw_test"
            dir = "disk0:" + test_dir
            REMOVE_DIR = re.compile(re.escape("Remove directory filename [{}]?".format(test_dir)))
            DELETE_CONFIRM = re.compile(re.escape("Delete {}/{}[confirm]".format(filesystem, test_dir)))
            REMOVE_ERROR = re.compile(re.escape("%Error Removing dir {} (Directory doesnot exist)".format(test_dir)))

            command = "rmdir {}".format(dir)
            events = [device.prompt, REMOVE_DIR, DELETE_CONFIRM, REMOVE_ERROR, pexpect.TIMEOUT]
            transitions = [
                (REMOVE_DIR, [0], 1, send_newline, 5),
                (DELETE_CONFIRM, [1], 2, send_newline, 5),
                # if dir does not exist initially it's ok
                (REMOVE_ERROR, [0], 2, None, 0),
                (device.prompt, [2], -1, None, 0),
                (pexpect.TIMEOUT, [0, 1, 2], -1, error, 0)

            ]
            manager.log("Removing test directory from {} if exists".format(dir))
            if not device.run_fsm("DELETE_DIR", command, events, transitions, timeout=5):
                return False

        This FSM tries to remove directory from disk0:

        Args:
            name (str): Name of the state machine used for logging purposes. Can't be *None*
            command (str): The command sent to the device before FSM starts
            events (list): List of expected strings or pexpect.TIMEOUT exception expected from the device.
            transitions (list): List of tuples in defining the state machine transitions.
            timeout (int): Default timeout between states in seconds.

        The transition tuple format is as follows::

            (event, [list_of_states], next_state, action, timeout)

        - event (str): string from the `events` list which is expected to be received from device.
        - list_of_states (list): List of FSM states that triggers the action in case of event occurrence.
        - next_state (int): Next state for FSM transition.
        - action (func): function to be executed if the current FSM state belongs to `list_of_states` and the `event`
          occurred. The action can be also *None* then FSM transits to the next state without any action. Action
          can be also the exception, which is raised and FSM stops.

        The example action::

            def send_newline(ctx):
                ctx.ctrl.sendline()
                return True

            def error(ctx):
                ctx.message = "Filesystem error"
                return False

            def readonly(ctx):
                ctx.message = "Filesystem is readonly"
                return False

        The ctx object description refer to :class:`condoor.controllers.fsm.FSM`.

        If the action returns True then the FSM continues processing. If the action returns False then FSM stops
        and the error message passed back to the ctx object is posted to the log.


        The FSM state is the integer number. The FSM starts with initial ``state=0`` and finishes if the ``next_state``
        is set to -1.

        If action returns False then FSM returns False. FSM returns True if reaches the -1 state.

        """

        self._send_command(command)
        fsm = FSM(name, self.ctrl, events, transitions, timeout=timeout)
        return fsm.run()

    @property
    def os_type(self):
        return self._get_os_type()

    def _get_os_type(self):
        for os_type in os_types:
            prompt_pattern = prompt_patterns[os_type]
            if re.match(prompt_pattern, self.ctrl.detected_target_prompt):
                return os_type
        else:
            return "unknown"

    def prepare_terminal_session(self):
        self.send('terminal len 0')
        #self.send('terminal width 0')

    def _compile_prompts(self):
        self.compiled_prompts = [re.compile(re.escape(prompt)) for prompt in self.ctrl.detected_prompts]

    def _send_command(self, cmd):
        self.ctrl.setecho(False)
        self.ctrl.send(cmd)
        self.ctrl.expect_exact([cmd, pexpect.TIMEOUT], timeout=15)
        self.ctrl.sendline()
        self.ctrl.setecho(True)

    def _execute_command(self, cmd, timeout, wait_for_string):
        with self.command_execution_pending:
            try:
                self._send_command(cmd)

                if wait_for_string:
                    self._wait_for_string(wait_for_string, timeout)
                else:
                    self.wait_for_prompt(timeout)

            except CommandSyntaxError as e:
                self._error("{}: '{}'".format(e.message, cmd))
                e.command = cmd
                raise

            except (CommandTimeoutError, pexpect.TIMEOUT) as e:
                self._error("Command timeout: '{}'".format(cmd))
                raise CommandTimeoutError(message="Command timeout", host=self.hostname, command=cmd)

            except ConnectionError as e:
                self._error("{}: '{}'".format(e.message, cmd))
                raise

            except pexpect.EOF:
                self._error("Unexpected session disconnect")
                raise ConnectionError("Unexpected session disconnect", host=self.hostname)

            except Exception as err:
                error_msg = str(err.message).splitlines()[0]
                self._error("Exception: {}:{}".format(err.__class__, error_msg))
                raise ConnectionError(message=error_msg, host=self.hostname)

    def _determine_config_mode(self, prompt):
        if 'config' in prompt:
            self.mode = 'config'
        elif 'admin' in prompt:
            self.mode = 'admin'
        else:
            self.mode = 'global'

        self._debug("Mode: {}".format(self.mode))

    def determine_hostname(self, prompt):
        self._debug("Hostname detecting not implemented for generic driver")

    # Actions for FSM

    @action
    def _expected_string_received(self, ctx):
        ctx.finished = True
        return True

    @action
    def _expected_prompt(self, ctx):
        prompt = self.ctrl.after
        self.ctrl.detected_target_prompt = prompt
        self._determine_config_mode(prompt)
        self.determine_hostname(prompt)
        ctx.finished = True
        return True

    @action
    def _unexpected_prompt(self, ctx):
        prompt = self.ctrl.after
        ctx.msg = "Received the jump host prompt: '{}'".format(prompt)
        self.ctrl.last_hop = self.ctrl.detected_prompts.index(prompt)
        self.ctrl.connected = False
        return False

    @action
    def _connection_closed(self, ctx):
        ctx.ctrl.connected = False
        return True

    @action
    def print_before(self, ctx):
        print(":".join("{:02x}".format(ord(c)) for c in ctx.ctrl.before))
        print(ctx.ctrl.before)
        print(self.compiled_prompts[-1].pattern.encode('string_escape'))

    @action
    def _stays_connected(self, ctx):
        self.ctrl.connected = True
        self.ctrl.last_hop = len(self.ctrl.hosts) - 1  # Authentication needed
        self.ctrl.last_pattern = PRESS_RETURN
        return True

    @action
    def _send_lf(self, ctx):
        ctx.ctrl.send('\r')
        return True

    @action
    def _send_line(self, ctx):
        ctx.ctrl.send('\r\n')
        return True

    @action
    def _send_yes(self, ctx):
        ctx.ctrl.sendline('yes')
        return True

    @action
    def _send_space(self, ctx):
        ctx.ctrl.send(' ')
        return True

    def wait_for_prompt(self, timeout=60):
        events = [self.command_syntax_re, self.connection_closed_re,
                  pexpect.TIMEOUT, pexpect.EOF, self.compiled_prompts[-1], self.press_return, self.more]

        # add detected prompts chain
        events += self.compiled_prompts[:-1]  # without target prompt

        self._debug("Waiting for prompt")

        transitions = [
            (self.command_syntax_re, [0], -1, CommandSyntaxError("Command unknown", self.hostname), 0),
            # (self.connection_closed_re, [0], -1, self._connection_closed, 10),
            (self.connection_closed_re, [0], 1, None, 10),
            (pexpect.TIMEOUT, [0], -1, CommandTimeoutError("Timeout waiting for prompt", self.hostname), 0),
            (pexpect.EOF, [0], -1, ConnectionError("Unexpected device disconnect", self.hostname), 0),
            (pexpect.EOF, [1], -1, self._connection_closed, 0),
            (self.more, [0], 0, self._send_space, 10),
            (self.compiled_prompts[-1], [0], -1, self._expected_prompt, 0),
            (self.press_return, [0], -1, self._stays_connected, 0)
        ]

        for prompt in self.compiled_prompts[:-1]:
            transitions.append((prompt, [0, 1], 0, self._unexpected_prompt, 0))

        sm = FSM("WAIT-4-PROMPT", self.ctrl, events, transitions, timeout=timeout)
        return sm.run()

    def _wait_for_string(self, expected_string, timeout=60):
        events = [self.command_syntax_re, self.connection_closed_re,
                  pexpect.TIMEOUT, pexpect.EOF, expected_string, self.press_return, self.more]

        # add detected prompts chain
        events += self.compiled_prompts[:-1]  # without target prompt

        self._debug("Waiting for string: '{}'".format(repr(expected_string)))

        transitions = [
            (self.command_syntax_re, [0], -1, CommandSyntaxError("Command unknown", self.hostname), 0),
            # (self.connection_closed_re, [0], -1, self._connection_closed, 10),
            (self.connection_closed_re, [0], 1, None, 10),
            (pexpect.TIMEOUT, [0], -1, CommandTimeoutError("Timeout waiting for string", self.hostname), 0),
            (pexpect.EOF, [0], -1, ConnectionError("Unexpected device disconnect", self.hostname), 0),
            (pexpect.EOF, [1], -1, self._connection_closed, 0),
            (self.more, [0], 0, self._send_space, 10),
            # (self.more, [2], 0, None, 10),
            (expected_string, [0], -1, self._expected_string_received, 0),
            (self.press_return, [0], -1, self._stays_connected, 0)
        ]

        for prompt in self.compiled_prompts[:-1]:
            transitions.append((prompt, [0, 1], 0, self._unexpected_prompt, 0))

        sm = FSM("WAIT-4-STR", self.ctrl, events, transitions, timeout=timeout)
        return sm.run()

    def prepare_prompt(self):
        self.prompt = self.ctrl.detected_target_prompt

    def _debug(self, msg):
        self.logger.debug("[{}]: {}".format(self.hostname, msg))

    def _error(self, msg):
        self.logger.error("[{}]: {}".format(self.hostname, msg))

    def _info(self, msg):
        self.logger.info("[{}]: {}".format(self.hostname, msg))

    def _warning(self, msg):
        self.logger.warning("[{}]: {}".format(self.hostname, msg))
