# =============================================================================
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

from ..exceptions import ConnectionError, ConnectionAuthenticationError, CommandSyntaxError, CommandTimeoutError

from ..controllers.fsm import FSM, action


class Connection(generic.Connection):
    """
    This is a platform specific implementation of based Driver class
    """
    platform = 'XR'
    target_prompt_components = ['prompt_dynamic', 'prompt_default', 'rommon', 'xml']

    def prepare_terminal_session(self):
        self.send('terminal exec prompt no-timestamp')
        self.send('terminal len 0')
        self.send('terminal width 0')

    # def determine_hostname(self, prompt):
    #     """
    #     RP/0/RP0/CPU0:Deploy#
    #     RP/0/RP0/CPU0:Deploy(config)#
    #     """
    #     try:
    #         self.hostname = prompt.split(":")[-1][:-1].split('(')[0]
    #         self._debug("Hostname detected: {}".format(self.hostname))
    #         if self.ctrl:
    #             self.ctrl.hostname = self.hostname
    #     except:
    #         self._warning("Unable to extract hostname from prompt: {}".format(prompt))

    def boot(self):
        pass

    def reload(self, rommon_boot_command="boot", reload_timeout=300):
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

        RELOAD = "admin reload location all"
        PROCEED = re.compile(re.escape("Proceed with reload? [confirm]"))

        DONE = re.compile(re.escape("[Done]"))
        CONFIGURATION_COMPLETED = re.compile("SYSTEM CONFIGURATION COMPLETED")
        CONFIGURATION_IN_PROCESS = re.compile("SYSTEM CONFIGURATION IN PROCESS")
        RECONFIGURE_USERNAME_PROMPT = re.compile("[Nn][Oo] root-system username is configured")
        # CONSOLE = re.compile("ios con0/RSP0/CPU0 is now available"))
        CONSOLE = re.compile("ios con[0|1]/RS?P[0-1]/CPU0 is now available")

        RELOAD_NA = re.compile("Reload to the ROM monitor disallowed from a telnet line")

        # FIXME: Not sure need to set echo to false
        self.ctrl.setecho(False)

        transitions_shared = [
            # here must be authentication
            (CONSOLE, [3, 4], 5, None, 600),
            (self.press_return_re, [5], 6, self._send_lf, 300),
            # if asks for username/password reconfiguration, go to success state and let plugin handle the rest.
            (RECONFIGURE_USERNAME_PROMPT, [6, 7], -1, None, 0),
            (CONFIGURATION_IN_PROCESS, [6], 7, None, 180),
            (CONFIGURATION_COMPLETED, [7], -1, self._return_and_authenticate, 0),
            (pexpect.TIMEOUT, [0, 1, 2], -1, ConnectionAuthenticationError("Unable to reload", self.hostname), 0),
            (pexpect.EOF, [0, 1, 2, 3, 4, 5], -1, ConnectionError("Device disconnected", self.hostname), 0),
            (pexpect.TIMEOUT, [6], 7, self._send_line, 180),
            (pexpect.TIMEOUT, [7], -1,
             ConnectionAuthenticationError("Unable to reconnect after reloading", self.hostname), 0),
        ]

        self.ctrl.sendline(RELOAD)
        events = [RELOAD_NA, RELOAD, DONE, PROCEED, CONFIGURATION_IN_PROCESS, self.rommon_re, self.press_return_re,
                  CONSOLE, CONFIGURATION_COMPLETED, RECONFIGURE_USERNAME_PROMPT,
                  pexpect.TIMEOUT, pexpect.EOF]
        transitions = [
            # Preparing system for backup. This may take a few minutes especially for large configurations.
            (RELOAD, [0], 1, self._send_lf, 300),
            (RELOAD_NA, [1], -1, self._reload_na, 0),
            (DONE, [1], 2, None, 120),
            (PROCEED, [2], 3, self._send_lf, reload_timeout),
            (self.rommon_re, [0, 3], 4, self._send_boot, 600),
        ] + transitions_shared

        fs = FSM("RELOAD", self.ctrl, events, transitions, timeout=10)
        return fs.run()

    def wait_for_prompt(self, timeout=60):
        # ASR with IOSXR specific error when cmd is longer than 256 characters
        _BUFFER_OVERFLOW = re.compile("Error: input buffer overflow")

        #                    0                         1                        2                       3
        events = [self.syntax_error_re, self.connection_closed_re, self.compiled_prompts[-1], self.press_return_re,
                  #        4           5                 6                7
                  self.more_re, _BUFFER_OVERFLOW, pexpect.TIMEOUT, pexpect.EOF]

        # add detected prompts chain
        events += self.compiled_prompts[:-1]  # without target prompt

        self._debug("Waiting for prompt")

        transitions = [
            (self.syntax_error_re, [0], -1, CommandSyntaxError("Command unknown", self.hostname), 0),
            (self.connection_closed_re, [0], 1, self._connection_closed, 10),
            (pexpect.TIMEOUT, [0], -1, CommandTimeoutError("Timeout waiting for prompt", self.hostname), 0),
            (pexpect.EOF, [0, 1], -1, ConnectionError("Unexpected device disconnect", self.hostname), 0),
            (self.more_re, [0], 0, self._send_space, 10),
            (self.compiled_prompts[-1], [0, 1], -1, self._expected_prompt, 0),
            (self.press_return_re, [0], -1, self._stays_connected, 0),
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
        ctx.ctrl.connect(start_hop=len(ctx.ctrl.hosts) - 1, spawn=False, detect_prompt=False)
        return True

    @action
    def _return_and_authenticate(self, ctx):
        self._send_lf(ctx)
        ctx.ctrl.connect(start_hop=len(ctx.ctrl.hosts) - 1, spawn=False, detect_prompt=False)
        return True

    @action
    def _reload_na(self, ctx):
        ctx.msg = "Reload to the ROM monitor disallowed from a telnet line. " \
                  "Set the configuration register boot bits to be non-zero."
        ctx.failed = True
        return False
