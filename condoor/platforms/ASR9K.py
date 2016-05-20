# =============================================================================
# asr9k
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

import generic
import pexpect

from ..exceptions import \
    ConnectionError,\
    ConnectionAuthenticationError, \
    CommandSyntaxError, \
    CommandTimeoutError

from ..controllers.fsm import FSM, action
from ..controllers.protocols.base import RECONFIGURE_USERNAME_PROMPT


class Connection(generic.Connection):
    """
    This is a platform specific implementation of based Driver class
    """
    platform = 'ASR9K'
    command_syntax_re = re.compile("\%(w+)?for a list of subcommands|"
                                   "\% Ambiguous command:|"
                                   "\% Invalid input detected")

    platform_prompt = generic.prompt_patterns['IOSXR']

    password_prompt = re.compile("[Pp]assword: ")
    username_prompt = re.compile("[Uu]sername: ")
    rommon_prompt = re.compile("rommon \d+ >")
    calvados_prompt = re.compile("sysadmin-vm:[0-3]_RS?P[0-1]#")

    rommon_boot_command = "boot"

    def prepare_prompt(self):
        prompt_re = re.compile(
            '((({})(\([^()]*\))?|'
            'sysadmin-vm:[0-3]_RS?P[0-1]:?.*)#|'
            'rommon \d+ >|'
            'RP/[0-3]/RS?P[0-1]/CPU[0-1]:ios)'.format(re.escape(self.ctrl.detected_target_prompt[:-1]))
        )
        self.compiled_prompts[-1] = prompt_re
        self.prompt = self.ctrl.detected_target_prompt

    def prepare_terminal_session(self):
        self.send('terminal exec prompt no-timestamp')
        self.send('terminal len 0')
        self.send('terminal width 0')

    def determine_hostname(self, prompt):
        """
        RP/0/RP0/CPU0:Deploy#
        RP/0/RP0/CPU0:Deploy(config)#
        sysadmin-vm:0_RP0:NCS-Deploy2#
        sysadmin-vm:0_RP0:NCS-Deploy2(config)#
        sysadmin-vm:0_RP0#
        sysadmin-vm:0_RP0(config)#
        sysadmin-vm:0_RSP0#

        """
        try:
            if re.match(self.calvados_prompt, prompt):
                self.hostname = 'NOT-SET'
            else:
                self.hostname = prompt.split(":")[-1][:-1].split('(')[0]
            self._debug("Hostname detected: {}".format(self.hostname))
            if self.ctrl:
                self.ctrl.hostname = self.hostname
        except:
            raise
            self._warning("Unable to extract hostname from prompt: {}".format(prompt))


    def boot(self):
        pass

    def enable(self, enable_password=None):
        pass

    def reload(self, rommon_boot_command="boot", reload_timeout=300, os="XR"):
        """
        RP/0/RSP0/CPU0:ASR9K-PE4#reload
        Tue Nov 10 14:43:11.488 UTC
        Some active software packages are not yet committed. Proceed?[confirm]
        Standby card not present or not Ready for failover. Proceed?[confirm]
        Preparing system for backup. This may take a few minutes especially for large configurations.
        Status report: node0_RSP0_CPU0: START TO BACKUP
        Status report: node0_RSP0_CPU0: BACKUP HAS COMPLETED SUCCESSFULLY
        [Done]
        """

        self.rommon_boot_command = rommon_boot_command

        if os == "eXR":
            ADMIN = "admin"
            RELOAD = "hw-module location all reload"
            CONFIRM_RELOAD = re.compile(re.escape("Reload hardware module ? [no,yes]"))
            # STANDBY_CONSOLE = ios con0/RSP1/CPU0 is in standby
            STBY_CONSOLE = re.compile("ios con[0|1]/RS?P[0-1]/CPU[0-9] is in standby")
        else:
            RELOAD = "admin reload location all"
            PROCEED = re.compile(re.escape("Proceed with reload? [confirm]"))

        DONE = re.compile(re.escape("[Done]"))
        CONFIGURATION_COMPLETED = re.compile("SYSTEM CONFIGURATION COMPLETED")
        CONFIGURATION_IN_PROCESS = re.compile("SYSTEM CONFIGURATION IN PROCESS")
        # CONSOLE = re.compile("ios con0/RSP0/CPU0 is now available"))
        CONSOLE = re.compile("ios con[0|1]/RS?P[0-1]/CPU0 is now available")

        RELOAD_NA = re.compile("Reload to the ROM monitor disallowed from a telnet line")

        # FIXME: Not sure need to set echo to false
        self.ctrl.setecho(False)

        transitions_shared = [
            # here must be authentication
            (CONSOLE, [3, 4], 5, None, 600),
            (self.press_return, [5], 6, self._send_lf, 300),
            # if asks for username/password reconfiguration, go to success state and let plugin handle the rest.
            (RECONFIGURE_USERNAME_PROMPT, [6, 7], -1, None, 0),
            (CONFIGURATION_IN_PROCESS, [6], 7, None, 180),
            (CONFIGURATION_COMPLETED, [7], -1, self._return_and_authenticate, 0),

            (pexpect.TIMEOUT, [0, 1, 2], -1,
             ConnectionAuthenticationError("Unable to reload", self.hostname), 0),
            (pexpect.EOF, [0, 1, 2, 3, 4, 5], -1,
             ConnectionError("Device disconnected", self.hostname), 0),
            (pexpect.TIMEOUT, [6], 7, self._send_line, 180),
            (pexpect.TIMEOUT, [7], -1,
             ConnectionAuthenticationError("Unable to reconnect after reloading", self.hostname), 0),
        ]

        if os == "eXR":
            self.send(cmd=ADMIN)
            self.ctrl.sendline(RELOAD)

            events = [RELOAD_NA, RELOAD, CONFIRM_RELOAD, DONE, STBY_CONSOLE, CONFIGURATION_IN_PROCESS, self.press_return,
                  CONSOLE, CONFIGURATION_COMPLETED, RECONFIGURE_USERNAME_PROMPT,
                  pexpect.TIMEOUT, pexpect.EOF]

            transitions = [
                # Preparing system for backup. This may take a few minutes especially for large configurations.
                (RELOAD, [0], 1, None, 120),
                (RELOAD_NA, [1], -1, self._reload_na, 0),
                (CONFIRM_RELOAD, [1], 2, self._send_yes, 120),
                (DONE, [2], 3, None, reload_timeout),
                (STBY_CONSOLE, [3], -1, None, 10)
            ] + transitions_shared

        else:
            self.ctrl.sendline(RELOAD)
            events = [RELOAD_NA, RELOAD, DONE, PROCEED, CONFIGURATION_IN_PROCESS, self.rommon_prompt, self.press_return,
                      CONSOLE, CONFIGURATION_COMPLETED, RECONFIGURE_USERNAME_PROMPT,
                      pexpect.TIMEOUT, pexpect.EOF]
            transitions = [
                # Preparing system for backup. This may take a few minutes especially for large configurations.
                (RELOAD, [0], 1, self._send_lf, 300),
                (RELOAD_NA, [1], -1, self._reload_na, 0),
                (DONE, [1], 2, None, 120),
                (PROCEED, [2], 3, self._send_lf, reload_timeout),
                (self.rommon_prompt, [0, 3], 4, self._send_boot, 600),
            ] + transitions_shared

        fs = FSM("RELOAD", self.ctrl, events, transitions, timeout=10)
        return fs.run()

    def wait_for_prompt(self, timeout=60):
        # ASR with IOSXR specific error when cmd is longer than 256 characters
        _BUFFER_OVERFLOW = "input buffer overflow"
        events = [self.command_syntax_re, self.connection_closed_re,
                  pexpect.TIMEOUT, pexpect.EOF, self.compiled_prompts[-1], self.press_return, self.more,
                  _BUFFER_OVERFLOW]

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
            (self.press_return, [0], -1, self._stays_connected, 0),
            (_BUFFER_OVERFLOW, [0], -1, CommandSyntaxError("Command too long", self.hostname), 0)
        ]

        for prompt in self.compiled_prompts[:-1]:
            transitions.append((prompt, [0, 1], 0, self._unexpected_prompt, 0))

        sm = FSM("WAIT-4-PROMPT", self.ctrl, events, transitions, timeout=timeout)
        return sm.run()

    @action
    def _send_boot(self, ctx):
        ctx.ctrl.sendline(self.rommon_boot_command)
        return True

    @action
    def _authenticate(self, ctx):
        ctx.ctrl.connect(start_hop=len(ctx.ctrl.hosts)-1, spawn=False, detect_prompt=False)
        return True

    @action
    def _return_and_authenticate(self, ctx):
        self._send_lf(ctx)
        ctx.ctrl.connect(start_hop=len(ctx.ctrl.hosts)-1, spawn=False, detect_prompt=False)
        return True

    @action
    def _reload_na(self, ctx):
        ctx.msg = "Reload to the ROM monitor disallowed from a telnet line. " \
                  "Set the configuration register boot bits to be non-zero."
        ctx.failed = True
        return False