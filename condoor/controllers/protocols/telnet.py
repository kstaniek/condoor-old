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

from base import Protocol

from condoor.controllers.fsm import FSM
from condoor.utils import pattern_to_str
from condoor.actions import a_send, a_send_line, a_send_password, a_authentication_error, a_unable_to_connect,\
    a_save_last_pattern

from condoor.exceptions import ConnectionError, ConnectionTimeoutError


# Telnet connection initiated
ESCAPE_CHAR = "Escape character is|Open"
# Connection refused i.e. line busy on TS
CONNECTION_REFUSED = re.compile("Connection refused")
PASSWORD_OK = "[Pp]assword [Oo][Kk]"
AUTH_FAILED = "Authentication failed|not authorized|Login incorrect"


class Telnet(Protocol):
    def __init__(self, controller, device, spawn, prompt, get_pattern, account_manager, logfile):
        super(Telnet, self).__init__(controller, device, prompt, get_pattern, account_manager, logfile)
        command = "telnet {} {}".format(self.hostname, self.port)
        if spawn:
            self._spawn_session(command)

    def connect(self):
        #              0            1                              2                      3
        events = [ESCAPE_CHAR, self.press_return_pattern, self.standby_pattern, self.username_pattern,
                  #            4                   5                  6                     7
                  self.password_pattern, self.more_pattern, self.prompt_pattern, self.rommon_pattern,
                  #       8                              9              10
                  self.unable_to_connect_pattern, pexpect.TIMEOUT, PASSWORD_OK]

        transitions = [
            (ESCAPE_CHAR, [0], 1, None, 20),
            (self.press_return_pattern, [0, 1], 1, partial(a_send, "\r\n"), 10),
            (PASSWORD_OK, [0, 1], 1, partial(a_send, "\r\n"), 10),
            (self.standby_pattern, [0, 5], -1, ConnectionError("Standby console", self.hostname), 0),
            (self.username_pattern, [0, 1, 5, 6], -1, partial(a_save_last_pattern, self), 0),
            (self.password_pattern, [0, 1, 5], -1, partial(a_save_last_pattern, self), 0),
            (self.more_pattern, [0, 5], 7, partial(a_send, "q"), 10),
            # router sends it again to delete
            (self.more_pattern, [7], 8, None, 10),
            # (prompt, [0, 1, 5], 6, partial(a_send, "\r\n"), 10),
            (self.prompt_pattern, [0, 1, 5], 0, None, 10),
            (self.prompt_pattern, [6, 8, 5], -1, partial(a_save_last_pattern, self), 0),
            (self.rommon_pattern, [0, 1, 5], -1, partial(a_save_last_pattern, self), 0),
            (self.unable_to_connect_pattern, [0, 1], -1, a_unable_to_connect, 0),
            (pexpect.TIMEOUT, [0, 1], 5, partial(a_send, "\r\n"), 10),
            (pexpect.TIMEOUT, [5], -1, ConnectionTimeoutError("Connection timeout", self.hostname), 0)
        ]
        self._dbg(10, "EXPECTED_PROMPT={}".format(pattern_to_str(self.prompt_pattern)))
        sm = FSM("TELNET-CONNECT", self.ctrl, events, transitions, init_pattern=self.ctrl.last_pattern)
        return sm.run()

    def authenticate(self):
        #                      0                      1                    2                    3
        events = [self.username_pattern, self.password_pattern, self.prompt_pattern, self.rommon_pattern,
                  #       4             5             6              7                8
                  self.unable_to_connect_pattern, AUTH_FAILED, pexpect.TIMEOUT, pexpect.EOF]

        transitions = [
            (self.username_pattern, [0], 1, partial(a_send_line, self.username), 10),
            (self.username_pattern, [1], 1, None, 10),
            (self.password_pattern, [0, 1], 2, partial(a_send_password, self._acquire_password()), 20),
            (self.username_pattern, [2], -1, a_authentication_error, 0),
            (self.password_pattern, [2], -1, a_authentication_error, 0),
            (self.prompt_pattern, [0, 1, 2], -1, None, 0),
            (self.rommon_pattern, [0], -1, partial(a_send, "\r\n"), 0),
            (pexpect.TIMEOUT, [0], 1, partial(a_send, "\r\n"), 10),
            (pexpect.TIMEOUT, [2], -1, None, 0),
            (AUTH_FAILED, [2], -1, a_authentication_error, 0),
            (pexpect.TIMEOUT, [3, 7], -1, ConnectionTimeoutError("Connection Timeout", self.hostname), 0),
        ]
        self._dbg(10, "EXPECTED_PROMPT={}".format(pattern_to_str(self.prompt_pattern)))
        sm = FSM("TELNET-AUTH", self.ctrl, events, transitions, init_pattern=self.last_pattern)
        self.try_read_prompt(1)
        return sm.run()

    def disconnect(self):
        # self.ctrl.sendcontrol(']')
        # self.ctrl.sendline('quit')
        self.ctrl.send(chr(4))

    def _dbg(self, level, msg):
        self.logger.log(level, "[{}]: [TELNET]: {}".format(self.ctrl.hostname, msg))


class TelnetConsole(Telnet):
    def connect(self):
        #              0            1                    2                      3
        events = [ESCAPE_CHAR, self.press_return_pattern, self.standby_pattern, self.username_pattern,
                  #            4                   5                  6                     7
                  self.password_pattern, self.more_pattern, self.prompt_pattern, self.rommon_pattern,
                  #       8                 9              10             11
                  self.unable_to_connect_pattern, pexpect.TIMEOUT, PASSWORD_OK]

        transitions = [
            (ESCAPE_CHAR, [0], 1, partial(a_send, "\r\n"), 20),
            (self.press_return_pattern, [0, 1], 1, partial(a_send, "\r\n"), 10),
            (PASSWORD_OK, [0, 1], 1, partial(a_send, "\r\n"), 10),
            (self.standby_pattern, [0, 5], -1, ConnectionError("Standby console", self.hostname), 0),
            (self.username_pattern, [0, 1, 5, 6], -1, partial(a_save_last_pattern, self), 0),
            (self.password_pattern, [0, 1, 5], -1, partial(a_save_last_pattern, self), 0),
            (self.more_pattern, [0, 5], 7, partial(a_send, "q"), 10),
            # router sends it again to delete
            (self.more_pattern, [7], 8, None, 10),
            # (prompt, [0, 1, 5], 6, partial(a_send, "\r\n"), 10),
            (self.prompt_pattern, [0, 1, 5], 0, None, 10),
            (self.prompt_pattern, [6, 8, 5], -1, partial(a_save_last_pattern, self), 0),
            (self.rommon_pattern, [0, 1, 5], -1, partial(a_save_last_pattern, self), 0),
            (self.unable_to_connect_pattern, [0, 1], -1, a_unable_to_connect, 0),
            (pexpect.TIMEOUT, [0, 1], 5, partial(a_send, "\r\n"), 10),
            (pexpect.TIMEOUT, [5], -1, ConnectionTimeoutError("Connection timeout", self.hostname), 0)
        ]
        self._dbg(10, "EXPECTED_PROMPT={}".format(pattern_to_str(self.prompt_pattern)))
        sm = FSM("TELNET-CONNECT-CONSOLE", self.ctrl, events, transitions, init_pattern=self.ctrl.last_pattern)
        return sm.run()

    def _dbg(self, level, msg):
        self.logger.log(level, "[{}]: [TELNET-CONNECT-CONSOLE]: {}".format(self.ctrl.hostname, msg))
