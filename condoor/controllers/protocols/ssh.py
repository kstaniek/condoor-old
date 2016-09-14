# =============================================================================
# ssh
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
import pexpect

from base import Protocol
from ..fsm import FSM, action
from ...utils import pattern_to_str
from condoor.actions import a_send_password, a_authentication_error

from ...exceptions import ConnectionAuthenticationError, ConnectionError, ConnectionTimeoutError


MODULUS_TOO_SMALL = "modulus too small"
PROTOCOL_DIFFER = "Protocol major versions differ"
NEWSSHKEY = "fingerprint is"
KNOWN_HOSTS = "added.*to the list of known hosts"
HOST_KEY_FAILED = "key verification failed"


class SSH(Protocol):
    def __init__(self, controller, device, spawn, prompt, get_pattern, account_manager, logfile):
        super(SSH, self).__init__(controller, device, prompt, get_pattern, account_manager, logfile)
        command = self._get_command()
        if spawn:
            self._spawn_session(command)

    def _get_command(self, version=2):
        if self.username:
            command = "ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -{} -p {} {}@{}".format(
                version, self.port, self.username, self.hostname
            )
        else:
            command = "ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -{} -p {} {}".format(
                version, self.port, self.hostname
            )
        return command

    def connect(self):
        #                      0                    1                 2                 3
        events = [self.password_pattern, self.prompt_pattern, self.unable_to_connect_pattern,
                  #   4           5               6               7                   8
                  NEWSSHKEY, KNOWN_HOSTS, HOST_KEY_FAILED, MODULUS_TOO_SMALL, PROTOCOL_DIFFER,
                  #      9
                  pexpect.TIMEOUT]

        transitions = [
            (self.password_pattern, [0, 1, 4, 5], -1, self.save_pattern, 0),
            (self.prompt_pattern, [0], -1, self.save_pattern, 0),
            #  cover all messages indicating that connection was not set up
            (self.unable_to_connect_pattern, [0], -1, self.unable_to_connect, 0),
            (NEWSSHKEY, [0], 1, self.send_yes, 10),
            (KNOWN_HOSTS, [0, 1], 0, None, 0),
            (HOST_KEY_FAILED, [0], -1, ConnectionError("Host key failed", self.hostname), 0),
            (MODULUS_TOO_SMALL, [0], 0, self.fallback_to_sshv1, 0),
            (PROTOCOL_DIFFER, [0], 4, self.fallback_to_sshv1, 0),
            (PROTOCOL_DIFFER, [4], -1, ConnectionError("Protocol version differs", self.hostname), 0),
            (pexpect.TIMEOUT, [0], 5, self.send_new_line, 10),
            (pexpect.TIMEOUT, [5], -1, ConnectionTimeoutError("Connection timeout", self.hostname), 0)

        ]
        self._dbg(10, "EXPECTED_PROMPT={}".format(pattern_to_str(self.prompt_pattern)))
        sm = FSM("SSH-CONNECT", self.ctrl, events, transitions, timeout=30, searchwindowsize=160)
        return sm.run()

    def authenticate(self):
        #              0                     1                    2                3
        events = [self.press_return_pattern, self.password_pattern, self.prompt_pattern, pexpect.TIMEOUT]

        transitions = [
            (self.press_return_pattern, [0, 1], 1, self.send_new_line, 10),
            (self.password_pattern, [0], 1, partial(a_send_password, self._acquire_password()), 20),
            (self.password_pattern, [1], -1, a_authentication_error, 0),
            (self.prompt_pattern, [0, 1], -1, None, 0),
            (pexpect.TIMEOUT, [1], -1,
             ConnectionError("Error getting device prompt") if self.ctrl.is_target else self.send_new_line, 0)
        ]

        self._dbg(10, "EXPECTED_PROMPT={}".format(pattern_to_str(self.prompt_pattern)))

        sm = FSM("SSH-AUTH", self.ctrl, events, transitions, init_pattern=self.last_pattern, timeout=30)
        sm.run()

        self.try_read_prompt(1)
        return True

    def disconnect(self):
        self.ctrl.sendline('\x03')

    @action
    def send_yes(self, ctx):
        ctx.ctrl.sendline("yes")
        return True

    @action
    def fallback_to_sshv1(self, ctx):
        command = self._get_command(version=1)
        self._spawn_session(command)
        return True

    def _dbg(self, level, msg):
        self.logger.log(
            level, "[{}]: [SSH]: {}".format(self.ctrl.hostname, msg)
        )
