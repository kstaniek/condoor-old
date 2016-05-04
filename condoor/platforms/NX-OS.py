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
    platform = 'NX-OS'
    command_syntax_re = re.compile("% Invalid command at '\^' marker\.|"
                                   "% Incomplete command at '\^' marker\.")

    platform_prompt = generic.prompt_patterns['NX-OS']

    password_prompt = re.compile("Password: ")
    username_prompt = re.compile("login: ")
    rommon_prompt = re.compile("loader >")
    standby_console = re.compile("\(standby\)")

    def prepare_prompt(self):
        mode = self.ctrl.detected_target_prompt[-1]

        # previously: '({})(\([^()]*\))?[#|>]'
        # It is assumed that session stays in privilege mode
        prompt_re = re.compile('({})(\([^()]*\))?#'.format(
            re.escape(self.ctrl.detected_target_prompt[:-1])))
        self.compiled_prompts[-1] = prompt_re
        self.prompt = self.ctrl.detected_target_prompt

    def determine_hostname(self, prompt):
        result = re.search(r"^(.*)#", prompt)
        if result:
            self.hostname = result.group(1)
            self._debug("Hostname detected: {}".format(self.hostname))

    def prepare_terminal_session(self):
        self.send('terminal len 0')
        self.send('terminal width 511')

    def reload(self, save_config=True):
        """
        !!!WARNING! there is unsaved configuration!!!
        This command will reboot the system. (y/n)?  [n]
        """
        if save_config:
            self.send("copy running-config startup-config")
        self.send("reload", wait_for_string="This command will reboot the system")
        self.ctrl.sendline("y")

    def enable(self, enable_password=None):
        pass
