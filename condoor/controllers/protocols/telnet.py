# =============================================================================
# telnet
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

from base import *
from ..fsm import FSM, action

from ...exceptions import \
    ConnectionError, \
    ConnectionTimeoutError

# Telnet connection initiated
ESCAPE_CHAR = "Escape character is|Open"
# Connection refused i.e. line busy on TS
CONNECTION_REFUSED = re.compile("Connection refused")


class Telnet(Protocol):
    def __init__(self, controller, device, spawn, account_manager, logfile):
        super(Telnet, self).__init__(controller,
                                     device,
                                     account_manager,
                                     logfile)
        command = "telnet {} {}".format(
            self.hostname, self.port
        )
        if spawn:
            self._spawn_session(command)

    def connect(self):

        if self.ctrl.is_target:
            prompt = self.ctrl.platform.platform_prompt
            rommon_prompt = self.ctrl.platform.rommon_prompt
            more = self.ctrl.platform.more
            password_prompt = self.ctrl.platform.password_prompt
            username_prompt = self.ctrl.platform.username_prompt
            standby_console = self.ctrl.platform.standby_console

        else:
            prompt = SHELL_PROMPT
            rommon_prompt = SHELL_PROMPT
            more = "!@#!@#"  # find another solution
            password_prompt = PASSWORD_PROMPT
            username_prompt = USERNAME_PROMPT
            standby_console = "!@#!@#"
        #              0            1               2                3              4            5      6
        events = [ESCAPE_CHAR, PRESS_RETURN, standby_console, username_prompt, password_prompt, more, prompt,
                  #     7                8                 9               10         11
                  rommon_prompt, UNABLE_TO_CONNECT, RESET_BY_PEER, pexpect.TIMEOUT, PASSWORD_OK]

        transitions = [
            (ESCAPE_CHAR, [0], 1, None, 20),
            (PRESS_RETURN, [0, 1], 1, self.send_new_line, 10),
            (PASSWORD_OK, [0, 1], 1, self.send_new_line, 10),
            (standby_console, [0, 5], -1, ConnectionError("Standby console", self.hostname), 0),
            (username_prompt, [0, 1, 5, 6], -1, self.save_pattern, 0),
            (password_prompt, [0, 1, 5], -1, self.save_pattern, 0),
            (more, [0, 5], 7, self.send_q, 10),
            # router sends it again to delete
            (more, [7], 8, None, 10),
            # (prompt, [0, 1, 5], 6, self.send_new_line, 10),
            (prompt, [0, 1, 5], 0, None, 10),
            (prompt, [6, 8, 5], -1, self.save_pattern, 0),
            (rommon_prompt, [0, 1], -1, self.save_pattern, 0),
            (UNABLE_TO_CONNECT, [0], -1, self.unable_to_connect, 0),
            (RESET_BY_PEER, [0, 1], -1, self.unable_to_connect, 0),
            (pexpect.TIMEOUT, [0, 1], 5, self.send_new_line, 10),
            (pexpect.TIMEOUT, [5], -1, ConnectionTimeoutError("Connection timeout", self.hostname), 0)
        ]
        sm = FSM("TELNET-CONNECT", self.ctrl, events, transitions, init_pattern=self.ctrl.last_pattern)
        return sm.run()

    def authenticate(self, prompt=None):
        if self.ctrl.is_target:
            prompt = self.ctrl.platform.platform_prompt
            rommon_prompt = self.ctrl.platform.rommon_prompt
            password_prompt = self.ctrl.platform.password_prompt
            username_prompt = self.ctrl.platform.username_prompt
        else:
            if prompt is None:
                prompt = SHELL_PROMPT
            rommon_prompt = SHELL_PROMPT
            password_prompt = PASSWORD_PROMPT
            username_prompt = USERNAME_PROMPT

        events = [username_prompt, password_prompt, prompt, rommon_prompt, UNABLE_TO_CONNECT, CONNECTION_REFUSED,
                  RESET_BY_PEER, PERMISSION_DENIED, AUTH_FAILED,
                  pexpect.TIMEOUT, pexpect.EOF]

        transitions = [
            (username_prompt, [0], 1, self.send_username, 10),
            (username_prompt, [1], 1, None, 10),
            (password_prompt, [0, 1], 2, self.send_pass, 20),
            (username_prompt, [2], -1, self.authentication_error, 0),
            (prompt, [0, 1, 2], -1, None, 0),
            (rommon_prompt, [0], -1, self.send_new_line, 0),
            (pexpect.TIMEOUT, [0], 1, self.send_new_line, 10),
            (pexpect.TIMEOUT, [2], -1, None, 0),
            (pexpect.TIMEOUT, [6], -1, ConnectionError("Unable to get shell prompt", self.hostname), 0),
            (pexpect.TIMEOUT, [3, 7], -1,  ConnectionTimeoutError("Connection Timeout", self.hostname), 0),
        ]

        if isinstance(prompt, str):
            self._dbg(10, "EXPECTED_PROMPT={}".format(prompt))
        elif prompt is not None:
            self._dbg(10, "EXPECTED_PROMPT={}".format(prompt.pattern))

        sm = FSM("TELNET-AUTH", self.ctrl, events, transitions, init_pattern=self.last_pattern)
        self.try_read_prompt(1)
        return sm.run()

    @action
    def set_custom_prompt_ps1(self, ctx):
        ctx.ctrl.sendline('PS1="{}"'.format("CONDORPROMPT"))
        ctx.timeout = 5
        return True

    @action
    def set_custom_prompt(self, ctx):
        ctx.ctrl.sendline('set prompt="{}"'.format("CONDORPROMPT"))
        ctx.timeout = 5
        return True

    @action
    def error(self, ctx):
        ctx.failed = True
        return False

    def disconnect(self):
        self.ctrl.sendcontrol(']')
        self.ctrl.sendline('quit')

    def _dbg(self, level, msg):
        self.logger.log(
            level, "[{}]: [TELNET]: {}".format(self.ctrl.hostname, msg)
        )