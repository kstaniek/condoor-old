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
from functools import partial
from threading import Lock

import pexpect

from condoor.actions import a_send, a_connection_closed, a_stays_connected, a_unexpected_prompt, a_expected_prompt,\
    a_expected_string_received
from condoor.patterns import YPatternManager
from condoor.controllers.fsm import FSM
from condoor.exceptions import ConnectionError, CommandError, CommandSyntaxError, CommandTimeoutError
from condoor.utils import parse_inventory


class Connection(object):
    platform = 'generic'
    inventory_cmd = None
    target_prompt_components = ['prompt_dynamic']

    def __init__(self, name, hosts, controller_class, logger, is_console=False, account_manager=None):
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
        self._os_type = 'unknown'
        self.mode = None
        self.compiled_prompts = []
        self.detected_prompts = []
        self.pattern_manager = YPatternManager()
        self.is_console = is_console
        self.prompt = self.pattern_manager.get_pattern('generic', 'prompt')
        self.is_rommon = False
        self.udi = parse_inventory()

        for _ in xrange(len(self.hosts) + 1):
            self.compiled_prompts.append(None)
            self.detected_prompts.append(None)
        self.compiled_prompts[0] = "FaKePrOmPt"
        self.detected_prompts[0] = "FaKePrOmPt"

        self.prompt_re = self.pattern_manager.get_pattern(self.platform, 'prompt')
        self.syntax_error_re = self.pattern_manager.get_pattern(self.platform, 'syntax_error')
        self.connection_closed_re = self.pattern_manager.get_pattern(self.platform, 'connection_closed')
        self.press_return_re = self.pattern_manager.get_pattern(self.platform, 'press_return')
        self.more_re = self.pattern_manager.get_pattern(self.platform, 'more')
        self.rommon_re = self.pattern_manager.get_pattern(self.platform, 'rommon')
        self.buffer_overflow = self.pattern_manager.get_pattern(self.platform, 'buffer_overflow')

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
            self.ctrl = self.ctrl_class(self.hosts, self.account_manager, logfile=logfile)
            self.ctrl.logger = self.logger
            self.ctrl.platform = self
            self._info("Connecting to {} using {} driver".format(self.__repr__(), self.platform))
            self._compile_prompts()
            self.connected = self.ctrl.connect()

        if self.connected:
            self._info("Connected to {}".format(self.__repr__()))
            self._detect_rommon(self.ctrl.detected_target_prompt)
            if self.is_rommon:
                raise ConnectionError("Device in rommon", self.hostname)
            self._compile_prompts()
            self.prepare_prompt()
            self.enable()
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

    def send_xml(self, command, timeout=60):
        """
        Handle error i.e.
        ERROR: 0x24319600 'XML-TTY' detected the 'informational' condition
        'The XML TTY Agent has not yet been started.
        Check that the configuration 'xml agent tty' has been committed.'
        """
        self._debug("Starting XML TTY Agent")
        result = self.send("xml")
        self._info("XML TTY Agent started")

        result = self.send(command, timeout=timeout)
        self.ctrl.sendcontrol('c')
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
        self._info("Priviledge mode not supported on {} platform".format(self.platform))

    def reload(self, rommon_boot_command="boot", reload_timeout=300):
        """This method reloads the device and waits for device to boot up. It post the informational message to the
        log if not implemented by device driver."""

        self._info("Reload not implemented on {} platform".format(self.platform))

    def run_fsm(self, name, command, events, transitions, timeout, max_transitions=20):
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
            max_transitions (int): Default maximum number of transitions allowed for FSM.

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
        fsm = FSM(name, self.ctrl, events, transitions, timeout=timeout, max_transitions=max_transitions)
        return fsm.run()

    def prepare_terminal_session(self):
        self.send('terminal len 0')

    def prepare_prompt(self):
        detected_target_prompt = self.detected_prompts[-1]
        patterns = [self.pattern_manager.get_pattern(
            self.platform, pattern_name, compiled=False) for pattern_name in self.target_prompt_components]

        patterns_re = "|".join(patterns).format(prompt=re.escape(detected_target_prompt[:-1]))

        try:
            prompt_re = re.compile(patterns_re)
        except re.error as e:
            raise RuntimeError("Pattern compile error: {} ({}:{})".format(e.message, self.platform, patterns_re))

        self.compiled_prompts[-1] = prompt_re
        self.prompt = self.ctrl.detected_target_prompt
        self._debug("Dynamic prompt: '{}'".format(prompt_re.pattern))

    def collect_udi(self):
        try:
            inventory = self.send(self.inventory_cmd)
        except (CommandError, ConnectionError):
            self._debug("UDI not collected")
            return None

        if inventory:
            self.udi = parse_inventory(inventory)

    def _detect_rommon(self, prompt):
        if prompt:
            result = re.search(self.rommon_re, prompt)
            if result:
                self.is_rommon = True
                self._debug('Rommon detected')
                return

        self.is_rommon = False

    def _compile_prompts(self):
        self.compiled_prompts = [re.compile(re.escape(prompt)) if prompt else None for prompt in self.detected_prompts]
        self._debug("Prompts compiled")

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
                    success = self._wait_for_string(wait_for_string, timeout)
                else:
                    success = self.wait_for_prompt(timeout)

                if not success:
                    self._error("Unexpected session disconnect during '{}' "
                                "command execution".format(cmd))
                    raise ConnectionError("Unexpected session disconnect", host=self.hostname)

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
                error_msg = str(err)
                self._error("Exception: {}:{}".format(err.__class__, error_msg))
                raise ConnectionError(message=error_msg, host=self.hostname)

    def determine_config_mode(self, prompt):
        if 'config' in prompt:
            self.mode = 'config'
        elif 'admin' in prompt:
            self.mode = 'admin'
        else:
            self.mode = 'global'

        self._debug("Mode: {}".format(self.mode))

    def determine_hostname(self, prompt):
        # self.prompt is a re pattern
        result = re.search(self.prompt_re, prompt)
        if result:
            self.hostname = result.group('hostname')
            self._debug("platform: {}".format(self.platform))
            self._debug("Hostname detected - generic: {}".format(self.hostname))
        else:
            self.hostname = 'not-set'
            self._debug("Hostname not set: {}".format(prompt))

    def wait_for_prompt(self, timeout=60):
        #                    0                         1                        2                        3
        events = [self.syntax_error_re, self.connection_closed_re, self.compiled_prompts[-1], self.press_return_re,
                  #        4           5                 6                7
                  self.more_re, pexpect.TIMEOUT, pexpect.EOF, self.buffer_overflow]

        # add detected prompts chain
        events += self.compiled_prompts[:-1]  # without target prompt

        self._debug("Waiting for prompt: {}".format(self.compiled_prompts[-1].pattern))

        transitions = [
            (self.syntax_error_re, [0], -1, CommandSyntaxError("Command unknown", self.hostname), 0),
            (self.connection_closed_re, [0], 1, a_connection_closed, 10),
            (pexpect.TIMEOUT, [0], -1, CommandTimeoutError("Timeout waiting for prompt", self.hostname), 0),
            (pexpect.EOF, [0, 1], -1, ConnectionError("Unexpected device disconnect", self.hostname), 0),
            (self.more_re, [0], 0, partial(a_send, " "), 10),
            (self.compiled_prompts[-1], [0, 1], -1, a_expected_prompt, 0),
            (self.press_return_re, [0], -1, a_stays_connected, 0),
            (self.buffer_overflow, [0], -1, CommandSyntaxError("Command too long", self.hostname), 0)
        ]

        for prompt in self.compiled_prompts[:-1]:
            transitions.append((prompt, [0, 1], 0, a_unexpected_prompt, 0))

        sm = FSM("WAIT-4-PROMPT", self.ctrl, events, transitions, timeout=timeout)
        return sm.run()

    def _wait_for_string(self, expected_string, timeout=60):
        #                    0                         1                      2                  3
        events = [self.syntax_error_re, self.connection_closed_re, self.press_return_re, self.more_re,
                  #      4                5             6
                  pexpect.TIMEOUT, pexpect.EOF, expected_string]

        # add detected prompts chain
        events += self.compiled_prompts[:-1]  # without target prompt

        self._debug("Waiting for string: '{}'".format(repr(expected_string)))

        transitions = [
            (self.syntax_error_re, [0], -1, CommandSyntaxError("Command unknown", self.hostname), 0),
            (self.connection_closed_re, [0], 1, a_connection_closed, 10),
            (pexpect.TIMEOUT, [0], -1, CommandTimeoutError("Timeout waiting for string", self.hostname), 0),
            (pexpect.EOF, [0, 1], -1, ConnectionError("Unexpected device disconnect", self.hostname), 0),
            (self.more_re, [0], 0, partial(a_send, " "), 10),
            (expected_string, [0], -1, a_expected_string_received, 0),
            (self.press_return_re, [0], -1, a_stays_connected, 0)
        ]

        for prompt in self.compiled_prompts[:-1]:
            transitions.append((prompt, [0, 1], 0, a_unexpected_prompt, 0))

        sm = FSM("WAIT-4-STR", self.ctrl, events, transitions, timeout=timeout)
        return sm.run()

    def _debug(self, msg):
        self.logger.debug("[{}]: {}".format(self.hostname, msg))

    def _error(self, msg):
        self.logger.error("[{}]: {}".format(self.hostname, msg))

    def _info(self, msg):
        self.logger.info("[{}]: {}".format(self.hostname, msg))

    def _warning(self, msg):
        self.logger.warning("[{}]: {}".format(self.hostname, msg))
