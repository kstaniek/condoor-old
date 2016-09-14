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

from functools import partial
import re
import pexpect

import generic
from ..exceptions import ConnectionError, ConnectionAuthenticationError

from actions import a_send, a_send_line, a_send_password


class Connection(generic.Connection):
    """
    This is a platform specific implementation of based Driver class
    """
    platform = 'IOS'
    target_prompt_components = ['prompt_dynamic', 'prompt_default', 'rommon']

    def __init__(self, name, hosts, controller_class, logger, is_console=False, account_manager=None):
        super(Connection, self).__init__(
            name, hosts, controller_class, logger, is_console=is_console, account_manager=account_manager)

        self.password_re = self.pattern_manager.get_pattern(self.platform, 'password')

    def _get_enable_password(self):
        hop_info = self.hosts[-1]
        enable_password = hop_info.enable_password
        if enable_password is None:
            enable_password = hop_info.password
        return enable_password

    def prepare_terminal_session(self):
        self.send('terminal len 0')
        self.send('terminal width 0')

    def _compile_prompts(self):
        super(Connection, self)._compile_prompts()
        if self.detected_prompts[-1]:
            self.compiled_prompts[-1] = re.compile(re.escape(self.detected_prompts[-1][:-1]) + "[#>]")
        self._debug("IOS prompt fixed")

    def reload(self, save_config=True):
        """
        CSM_DUT#reload

        System configuration has been modified. Save? [yes/no]: yes
        Building configuration...
        [OK]
        Proceed with reload? [confirm]
        """
        RELOAD_CMD = "reload"
        SAVE_CONFIG = re.compile(re.escape("System configuration has been modified. Save? [yes/no]: "))
        PROCEED = re.compile(re.escape("Proceed with reload? [confirm]"))

        response = "yes" if save_config else "no"

        events = [SAVE_CONFIG, PROCEED, pexpect.TIMEOUT, pexpect.EOF]

        transitions = [
            (SAVE_CONFIG, [0], 1, partial(a_send_line, response), 60),
            (PROCEED, [0, 1], -1, partial(a_send, "\r"), 10),
            # if timeout try to send the reload command again
            (pexpect.TIMEOUT, [0], 0, partial(a_send_line, RELOAD_CMD), 10),
            (pexpect.EOF, [0, 1], -1, None, 0)
        ]
        return self.run_fsm("IOS-RELOAD", RELOAD_CMD, events, transitions, timeout=10, max_transitions=5)

    def enable(self, enable_password=None):

        ENABLE_CMD = "enable"
        prompt = self.compiled_prompts[-1]
        enable_password = enable_password if enable_password else self._get_enable_password()

        events = [self.password_re, prompt, pexpect.TIMEOUT, pexpect.EOF]
        transitions = [
            (self.password_re, [0], 1, partial(a_send_password, enable_password), 10),
            (self.password_re, [1], -1, ConnectionAuthenticationError("Incorrect enable password", self.hostname), 0),
            (prompt, [0, 1, 2, 3], -1, None, 0),
            (pexpect.TIMEOUT, [0, 1, 2], -1,
             ConnectionAuthenticationError("Unable to get privilidge mode", self.hostname), 0),
            (pexpect.EOF, [0, 1, 2], -1, ConnectionError("Device disconnected", self.hostname), 0)
        ]

        return self.run_fsm("IOS-ENABLE", ENABLE_CMD, events, transitions, timeout=10, max_transitions=5)
