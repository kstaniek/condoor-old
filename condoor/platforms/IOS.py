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
    command_syntax_re = re.compile('\% Bad IP address or host name% Unknown command or computer name, '
                                   'or unable to find computer address|'
                                   '\% Ambiguous command:.*"|'
                                   '\% Type "show \?" for a list of subcommands|'
                                   "% Invalid input detected at '\^' marker\.")

    platform_prompt = generic.prompt_patterns['IOS']

    password_prompt = re.compile("Password: ")
    username_prompt = re.compile("Username: ")
    rommon_prompt = re.compile("(rommon \d+ >)|(rommon>)")

    def _get_enable_password(self):
        hop_info = self.hosts[-1]
        enable_password = hop_info.enable_password
        if enable_password is None:
            enable_password = hop_info.password
        return enable_password

    def prepare_prompt(self):
        mode = self.ctrl.detected_target_prompt[-1]

        # previously: '({})(\([^()]*\))?[#|>]'
        # It is assumed that session stays in privilege mode
        prompt_re = re.compile('({})(\([^()]*\))?#'.format(
            re.escape(self.ctrl.detected_target_prompt[:-1])))
        self.compiled_prompts[-1] = prompt_re
        self.prompt = self.ctrl.detected_target_prompt

        if mode == '>':
            self.enable()

    def determine_hostname(self, prompt):
        result = re.search(r"^(.*)[#|>]", prompt)
        if result:
            self.hostname = result.group(1)
            self._debug("Hostname detected: {}".format(self.hostname))

    def prepare_terminal_session(self):
        self.send('terminal len 0')
        self.send('terminal width 0')

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
        ENABLE = "enable"
        self.ctrl.send("enable")
        prompt = self.compiled_prompts[-1]

        events = [ENABLE, self.password_prompt, prompt, pexpect.TIMEOUT, pexpect.EOF]
        transitions = [
            (ENABLE, [0], 1, self._send_lf, 10),
            (self.password_prompt, [1], 2, self._send_enable_password, 10),
            (self.password_prompt, [2], -1,
             ConnectionAuthenticationError("Incorrect enable password", self.hostname), 0),
            (prompt, [1, 2, 3], -1, None, 0),
            (pexpect.TIMEOUT, [0, 1, 2], -1,
             ConnectionAuthenticationError("Unable to get enable mode", self.hostname), 0),
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
