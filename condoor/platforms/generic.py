# =============================================================================
# generic.py
#
# Copyright (c)  2015, Cisco Systems
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

from ..utils import to_list
from ..exceptions import \
    ConnectionError,\
    ConnectionTimeoutError, \
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

#_PROMPT_IOSXR_RE = re.compile('(\w+/\w+/\w+/\w+:.*?)(\([^()]*\))?#')
#_PROMPT_IOS_RE = re.compile('\w+>|\w+#')


prompt_patterns = {
    'IOSXR': re.compile('(RP/\d+/RS?P[0-1]/CPU[0-3]:.*?)(\([^()]*\))?#'),
    'CALVADOS': re.compile("sysadmin-vm:[0-3]_RS?P[0-1]#"),
    'ROMMON': re.compile("rommon [A|B]?\d+ >"),
    'IOS': re.compile('[\w\-]+[#|>]')
}

os_types = ['IOSXR', 'CALVADOS', 'ROMMON', 'IOS']


def _c(ctx, msg):
    return "[{}]: {}".format(ctx, msg)


class Connection(object):
    """
    Generic connection driver providing the basic API to the physical devices.
    It implements the following methods:
        - connect
        - disconnect
        - send
        - send_xml

    The Driver class can be extended by the hardware specific classes.
    The derived classes can use different controller implementation
    providing additional flexibility.

    """
    platform = 'generic'
    shell_prompt = "\$\s?|>\s?|#\s?|\%\s?"
    connection_closed_re = re.compile("Connection closed")
    rommon_prompt = re.compile("rommon.*>")
    # platform_prompt = re.compile('[\r\n][\r\n]((\w+/\w+/\w+/\w+:.*?)(\([^()]*\))?#|.*?[#|>])')
    platform_prompt = re.compile('[\w\-]+[#|>]')

    password_prompt = re.compile("[P|p]assword:\s?")
    username_prompt = re.compile("([U|u]sername:\s|login:\s?)")

    command_syntax_re = re.compile('\% Bad IP address or host name% Unknown command or computer name, '
                                   'or unable to find computer address|'
                                   '\% Ambiguous command:.*"|"'
                                   '\% Type "show \?" for a list of subcommands'
                                   '\%(w+)?for a list of subcommands|'
                                   '\% Ambiguous command:|'
                                   '\% Invalid input detected')
    press_return = re.compile("Press RETURN to get started\.")
    more = re.compile(" --More-- ")

    def __init__(
            self,
            hostname,
            hosts,
            controller_class,
            logger,
            account_manager=None):
        """Initialize the Driver object.

         Args:
            hosts: Single object or list of HopInfo objects
            controller: Controller class used for low level device
                communication.
            account_manager: optional object providing the safe credentials
                management. If password is missing in the HopInfo
                during the connection setup the account_manager is used to
                retrieve the password.
            debug: debug level (0 - none .. 5 - debug)
            logfile: file handler descriptor (fd) for session log file.
        """

        self.hosts = to_list(hosts)
        self.account_manager = account_manager
        self.pending_connection = False
        self.connected = False
        self.command_execution_pending = Lock()
        self.ctrl = None
        self.ctrl_class = controller_class
        self.hostname = hostname
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
            self.ctrl = self.ctrl_class(self,  # delegation to controller
                                        self.hostname,
                                        self.hosts,
                                        self.account_manager,
                                        logfile=logfile)

            self.logger.info(
                _c(self.hostname, "Connecting to {}".format(self.__repr__())))
        self.connected = self.ctrl.connect()

        if self.connected:
            self.logger.info(
                _c(self.hostname, "Connected to {}".format(self.__repr__())))

            self._compile_prompts()
            self.prepare_prompt()
            self.prepare_terminal_session()

        else:
            raise ConnectionError(
                "Connection failed", self.hostname
            )

        return self.connected

    def disconnect(self):
        """
        Tear down the connection

        Args:
            None

        Returns:
            None

        """
        self.logger.info(
            _c(self.hostname, "Disconnecting from {}".format(self.__repr__())))
        self.ctrl.disconnect()
        self.connected = False
        self.pending_connection = False
        self.logger.info(_c(self.hostname, "Disconnected"))

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
            cmd (str): command string for execution
            timeout (int): timeout in seconds
            wait_for_string (str): this is optional string that driver
                waits for after command execution. If none the detected
                prompt will be used.

        Returns:
            A string containing the command output.
        """
        if self.connected:
            self.logger.debug(
                _c(self.hostname, "Sending command: '{}'".format(cmd)))

            try:
                self._execute_command(cmd, timeout, wait_for_string)
            except ConnectionError:
                self.logger.warn(
                    _c(self.hostname,
                        "Connection lost. Disconnecting."))
                self.disconnect()
                raise

            self.logger.info(
                _c(self.hostname,
                   "Command executed successfully: '{}'".format(cmd)))
            output = self.ctrl.before
            # if output.startswith(cmd):
            #    remove first line which contains the command itself
            #    second_line_index = output.find('\n') + 1
            #    output = output[second_line_index:]
            output = output.replace('\r', '')
            return output

        else:
            raise ConnectionError(
                "Device not connected", host=self.hostname)

    def send_xml(self, command):
        """
        Handle error i.e.
        ERROR: 0x24319600 'XML-TTY' detected the 'informational' condition
        'The XML TTY Agent has not yet been started.
        Check that the configuration 'xml agent tty' has been committed.'
        """
        self.logger.debug(_c(self.hostname, "Starting XML TTY Agent"))
        result = self.send("xml", wait_for_string=_PROMPT_XML)
        if result != '':
            return result
        self.logger.info(_c(self.hostname, "XML TTY Agent started"))

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
        self.logger.debug(_c(self.hostname, "Starting XML TTY Agent"))
        result = self.send("netconf", wait_for_string=']]>]]>')
        # if result != '':
        #    return result
        self.logger.info(_c(self.hostname, "XML TTY Agent started"))

        self.ctrl.send(command)
        #self.ctrl.expect("]]>]]>")
        self.ctrl.send("\r\n")
        self.ctrl.expect("]]>]]>")
        result = self.ctrl.before
        self.ctrl.sendcontrol('c')
        self.send()
        return result

    def enable(self):
        self.logger.info("Ignoring. Not supported on this platform")

    def run_fsm(self, name, command, events, transitions, timeout):
        self.ctrl.send(command)
        self.ctrl.expect_exact(command)
        self.ctrl.sendline()
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
        self.send('terminal width 0')

    def _compile_prompts(self):
        self.compiled_prompts = [re.compile(re.escape(prompt)) for prompt in self.ctrl.detected_prompts]

    def _execute_command(self, cmd, timeout, wait_for_string):
        with self.command_execution_pending:

            try:
                self.ctrl.setecho(False)
                self.ctrl.send(cmd)
                self.ctrl.expect_exact(cmd)
                self.ctrl.sendline()
                self.ctrl.setecho(True)
                if wait_for_string:
                    self.logger.debug(_c(
                        self.hostname,
                        "Waiting for string:'{}'".format(wait_for_string)))
                    self._wait_for_string(wait_for_string, 3, timeout)
                else:
                    self.wait_for_prompt(timeout)

            except CommandSyntaxError, e:
                self.logger.error(_c(
                    self.hostname,
                    "Syntax error: '{}'".format(cmd)))
                e.command = cmd
                raise

            except CommandTimeoutError, e:
                self.logger.error(_c(
                    self.hostname,
                    "Command timeout: '{}'".format(cmd)))
                e.command = cmd
                raise

            except ConnectionError:
                self.logger.error(_c(
                    self.hostname,
                    "Connection Error: '{}'".format(cmd)))
                raise

            except Exception, err:
                self.logger.error(_c(
                    self.hostname,
                    "Exception: '{}'".format(err)))
                raise ConnectionError(message=err, host=self.hostname)

    def _determine_config_mode(self, prompt):
        if 'config' in prompt:
            self.mode = 'config'
        elif 'admin' in prompt:
            self.mode = 'admin'
        else:
            self.mode = 'global'

        self.logger.debug(_c(
            self.hostname,
            "Mode: {}".format(self.mode)
        ))

    @action
    def _expected_prompt(self, ctx):
        prompt = self.ctrl.after
        self.ctrl.detected_target_prompt = prompt
        self._determine_config_mode(prompt)
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

    def wait_for_prompt(self, timeout=60):

        events = [self.command_syntax_re, self.connection_closed_re,
                  pexpect.TIMEOUT, pexpect.EOF, self.compiled_prompts[-1], self.press_return, self.more]
        # add detected prompts chain

        events += self.compiled_prompts[:-1]  # without target prompt

        self.logger.debug(_c(self.hostname, "Waiting for prompt"))

        transitions = [
            (self.command_syntax_re, [0], -1, CommandSyntaxError("Invalid input detected", self.hostname), 0),
            # (self.connection_closed_re, [0], -1, self._connection_closed, 10),
            (self.connection_closed_re, [0], 1, None, 10),
            (pexpect.TIMEOUT, [0], -1, CommandTimeoutError("Timeout waiting for prompt", self.hostname), 0),
            #(pexpect.TIMEOUT, [0], -1, self.print_before, 0),
            (pexpect.EOF, [0], -1, ConnectionError("Unexpected device disconnect", self.hostname), 0),
            (pexpect.EOF, [1], -1, self._connection_closed, 0),
            (self.more, [0], 0, self.send_space, 10),
            # (self.more, [2], 0, None, 10),
            (self.compiled_prompts[-1], [0], -1, self._expected_prompt, 0),
            (self.press_return, [0], -1, self._stays_connected, 0)
        ]

        for prompt in self.compiled_prompts[:-1]:
            transitions.append((prompt, [0, 1], 0, self._unexpected_prompt, 0))

        sm = FSM("WAIT-4-PROMPT", self.ctrl, events, transitions, timeout=timeout)
        return sm.run()

    @action
    def print_before(self, ctx):
        print(":".join("{:02x}".format(ord(c)) for c in ctx.ctrl.before))
        print(ctx.ctrl.before)
        print(self.compiled_prompts[-1].pattern.encode('string_escape'))

    @action
    def _stays_connected(self, ctx):
        #self.disconnect()
        self.ctrl.connected = True
        self.ctrl.last_hop = len(self.ctrl.hosts) - 1  # Authentication needed
        self.ctrl.last_pattern = PRESS_RETURN
        return True

    def _wait_for_string(self, expected_string, max_attempts=3, timeout=60):
        index = 0
        state = 0
        attempt = 0
        while attempt < max_attempts + 1:
            index = self.ctrl.expect_exact(
                [expected_string, _INVALID_INPUT, _INCOMPLETE_COMMAND,
                 pexpect.TIMEOUT,
                 _CONNECTION_CLOSED, pexpect.EOF], timeout=timeout,
                #searchwindowsize=len(expected_string)+10
            )
            self.logger.debug(_c(self.hostname,
                             "INDEX={}, STATE={}, ATTEMPT={}".format(
                                 index, state, attempt)))
            if index == 0:
                self.logger.debug(
                    _c(self.hostname,
                       "Received expected string: {}".format(expected_string)))
                if state == 0:
                    return
                if state == 1:
                    raise CommandSyntaxError(host=self.hostname)

            if index == 1:
                self.logger.warning(_c(self.hostname, "Invalid input detected"))

                # command syntax error so wait for prompt again
                state = 1
                continue

            if index == 2:
                self.logger.warning(_c(self.hostname, "Incomplete command"))

                # command syntax error so wait for prompt again
                state = 1
                continue

            if index == 3:
                self.logger.warning(
                    _c(self.hostname,
                       "Timeout waiting for '{}' ({}/{})".format(
                           expected_string, attempt, max_attempts)))
                # Trying to get prompt again
                self.ctrl.sendline()

            if index in [4, 5]:
                raise ConnectionError(
                    "Unexpected device disconnect", self.hostname)

            attempt += 1
        else:
            self.logger.error(_c(self.hostname, "Unexpected response received"))
            if index == 3:
                raise ConnectionTimeoutError(host=self.hostname)

    def prepare_prompt(self):
        self.prompt = self.ctrl.detected_target_prompt
        #self.compiled_prompt = re.compile(re.escape(self.ctrl.detected_target_prompt))
        #self.prompt = re.compile("\$|>|#")

    @action
    def _send_lf(self, ctx):
        ctx.ctrl.send('\r')
        return True

    @action
    def send_space(self, ctx):
        ctx.ctrl.send(' ')
        return True