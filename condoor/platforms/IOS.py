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

import logging
import re

import generic
from ..exceptions import ConnectionError, ConnectionAuthenticationError

from ..controllers.fsm import FSM, action
import pexpect


_logger = logging.getLogger(__name__)


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
        pass

    def enable(self, enable_password=None):
        self._send_command("enable")
        prompt = self.compiled_prompts[-1]

        events = [self.password_re, prompt, pexpect.TIMEOUT, pexpect.EOF]
        transitions = [
            (self.password_re, [0], 1, self._send_enable_password, 10),
            (self.password_re, [1], -1,
             ConnectionAuthenticationError("Incorrect enable password", self.hostname), 0),
            (prompt, [0, 1, 2, 3], -1, None, 0),
            (pexpect.TIMEOUT, [0, 1, 2], -1,
             ConnectionAuthenticationError("Unable to get privilidge mode", self.hostname), 0),
            (pexpect.EOF, [0, 1, 2], -1, ConnectionError("Device disconnected", self.hostname), 0)
        ]

        fs = FSM("IOS-ENABLE", self.ctrl, events, transitions, timeout=10)
        return fs.run()

    @action
    def _send_lf(self, ctx):
        ctx.ctrl.send('\r')
        return True

    @action
    def _send_enable_password(self, ctx):
        ctx.ctrl.setecho(False)
        ctx.ctrl.sendline(self._get_enable_password())
        ctx.ctrl.setecho(True)
        return True
