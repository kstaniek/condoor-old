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
from functools import partial
import re
import pexpect
import generic
from condoor.actions import a_reload_na, a_send, a_send_line, a_send_boot, a_return_and_reconnect
from condoor.controllers.fsm import FSM
from condoor.exceptions import ConnectionError, ConnectionAuthenticationError


class Connection(generic.Connection):
    """
    This is a platform specific implementation of based Driver class
    """
    platform = 'XR'
    inventory_cmd = 'admin show inventory chassis'
    target_prompt_components = ['prompt_dynamic', 'prompt_default', 'rommon', 'xml']

    def prepare_terminal_session(self):
        self.send('terminal exec prompt no-timestamp')
        self.send('terminal len 0')
        self.send('terminal width 0')

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
            (self.press_return_re, [5], 6, partial(a_send, "\r"), 300),
            # if asks for username/password reconfiguration, go to success state and let plugin handle the rest.
            (RECONFIGURE_USERNAME_PROMPT, [6, 7], -1, None, 0),
            (CONFIGURATION_IN_PROCESS, [6], 7, None, 180),
            (CONFIGURATION_COMPLETED, [7], -1, a_return_and_reconnect, 0),
            (pexpect.TIMEOUT, [0, 1, 2], -1, ConnectionAuthenticationError("Unable to reload", self.hostname), 0),
            (pexpect.EOF, [0, 1, 2, 3, 4, 5], -1, ConnectionError("Device disconnected", self.hostname), 0),
            (pexpect.TIMEOUT, [6], 7, partial(a_send_line, ""), 180),
            (pexpect.TIMEOUT, [7], -1,
             ConnectionAuthenticationError("Unable to reconnect after reloading", self.hostname), 0),
        ]

        self.ctrl.sendline(RELOAD)
        events = [RELOAD_NA, RELOAD, DONE, PROCEED, CONFIGURATION_IN_PROCESS, self.rommon_re, self.press_return_re,
                  CONSOLE, CONFIGURATION_COMPLETED, RECONFIGURE_USERNAME_PROMPT,
                  pexpect.TIMEOUT, pexpect.EOF]
        transitions = [
            # Preparing system for backup. This may take a few minutes especially for large configurations.
            (RELOAD, [0], 1, partial(a_send, "\r"), 300),
            (RELOAD_NA, [1], -1, a_reload_na, 0),
            (DONE, [1], 2, None, 120),
            (PROCEED, [2], 3, partial(a_send, "\r"), reload_timeout),
            (self.rommon_re, [0, 3], 4, partial(a_send_boot, rommon_boot_command), 600),
        ] + transitions_shared

        fs = FSM("RELOAD", self.ctrl, events, transitions, timeout=10)
        return fs.run()
