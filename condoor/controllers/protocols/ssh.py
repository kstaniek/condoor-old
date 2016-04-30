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

from base import *
import pexpect
from ..fsm import FSM, action

from ...exceptions import \
    ConnectionAuthenticationError, \
    ConnectionError, \
    ConnectionTimeoutError


MODULUS_TOO_SMALL = "modulus too small"
PROTOCOL_DIFFER = "Protocol major versions differ"
NEWSSHKEY = "fingerprint is"
KNOWN_HOSTS = "added.*to the list of known hosts"
HOST_KEY_FAILED = "key verification failed"


class SSH(Protocol):
    def __init__(self, controller, device, spawn, account_manager, logfile):
        super(SSH, self).__init__(controller, device, account_manager, logfile)

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

        if self.ctrl.is_target:
            prompt = self.ctrl.platform.platform_prompt
            rommon_prompt = self.ctrl.platform.rommon_prompt
            more = self.ctrl.platform.more
            password_prompt = self.ctrl.platform.password_prompt
            username_prompt = self.ctrl.platform.username_prompt

        else:
            prompt = SHELL_PROMPT
            rommon_prompt = SHELL_PROMPT
            more = "!@#!@#"  # find another solution
            password_prompt = PASSWORD_PROMPT

        events = [password_prompt, prompt, UNABLE_TO_CONNECT, RESET_BY_PEER,
                  NEWSSHKEY, KNOWN_HOSTS, HOST_KEY_FAILED, MODULUS_TOO_SMALL, PROTOCOL_DIFFER,
                  pexpect.TIMEOUT]

        transitions = [
            (password_prompt, [0, 1, 4], -1, self.save_pattern, 0),
            (prompt, [0], -1, self.save_pattern, 0),
            #  cover all messages indicating that connection was not set up
            (UNABLE_TO_CONNECT, [0], -1, self.unable_to_connect, 0),
            #  not sure when it happens - saw if there was session timeout on router
            (RESET_BY_PEER, [0], -1, self.unable_to_connect, 0),
            (NEWSSHKEY, [0], 1, self.send_yes, 10),
            (KNOWN_HOSTS, [1], 0, None, 0),
            (HOST_KEY_FAILED, [0], -1, ConnectionError("Host key failed", self.hostname), 0),
            (MODULUS_TOO_SMALL, [0], 0, self.fallback_to_sshv1, 0),
            (PROTOCOL_DIFFER, [0], 4, self.fallback_to_sshv1, 0),
            (PROTOCOL_DIFFER, [4], -1, ConnectionError("Protocol version differs", self.hostname), 0),
            (pexpect.TIMEOUT, [0], 5, self.send_new_line, 10),
            (pexpect.TIMEOUT, [5], -1, ConnectionTimeoutError("Connection timeout", self.hostname), 0)

        ]
        sm = FSM("SSH-CONNECT", self.ctrl, events, transitions, timeout=30)
        return sm.run()

    def authenticate(self, prompt=None):
        if self.ctrl.is_target:
            prompt = self.ctrl.platform.prompt
            rommon_prompt = self.ctrl.platform.rommon_prompt
            password_prompt = self.ctrl.platform.password_prompt

        else:
            if prompt is None:
                prompt = SHELL_PROMPT
            rommon_prompt = SHELL_PROMPT
            password_prompt = PASSWORD_PROMPT

        events = [PRESS_RETURN, password_prompt, prompt, pexpect.TIMEOUT]

        transitions = [
            (PRESS_RETURN, [0, 1], 1, self.send_new_line, 10),
            (password_prompt, [0], 1, self.send_pass, 20),
            (password_prompt, [1], -1, ConnectionAuthenticationError("Authentication error", self.hostname), 0),
            (prompt, [0, 1], -1, None, 0),
            (pexpect.TIMEOUT, [1], -1,
             ConnectionError("Error getting device prompt") if self.ctrl.is_target else self.send_new_line, 0)
        ]

        if isinstance(prompt, str):
            self._dbg(10, "EXPECTED_PROMPT={}".format(prompt))
        elif prompt is not None:
            self._dbg(10, "EXPECTED_PROMPT={}".format(prompt.pattern))

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