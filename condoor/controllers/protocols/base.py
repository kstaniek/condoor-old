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
import pexpect
import time

from ...exceptions import \
    ConnectionAuthenticationError, \
    ConnectionError, \
    ConnectionTimeoutError

from ..fsm import action


class Protocol(object):

    def __init__(self, controller, node_info, prompt, get_pattern, account_manager=None, logfile=None):
        self.protocol = node_info.protocol
        self.hostname = node_info.hostname
        self.port = node_info.port
        self.password = node_info.password

        self.ctrl = controller
        self.logfile = logfile
        self.account_manager = account_manager

        self.prompt = ''

        username = node_info.username
        if not username and self.account_manager:
            username = self.account_manager.get_username(self.hostname)

        self.username = username
        self.last_pattern = None
        self.logger = controller.logger

        self.prompt_pattern = prompt if prompt else get_pattern('prompt')
        self.username_pattern = get_pattern('username')
        self.password_pattern = get_pattern('password')
        self.more_pattern = get_pattern('more')
        self.rommon_pattern = get_pattern('rommon')
        self.standby_pattern = get_pattern('standby')
        self.press_return_pattern = get_pattern('press_return')
        self.unable_to_connect_pattern = get_pattern('unable_to_connect')

    def _spawn_session(self, command):
        self._dbg(10, "Executing command: '{}'".format(command))
        if self.ctrl._session and self.ctrl.isalive():
            try:
                self.ctrl.send(command)
                self.ctrl.expect_exact(command, timeout=20)
                self.ctrl.sendline()

            except pexpect.EOF:
                raise ConnectionError("Connection error", self.hostname)
            except pexpect.TIMEOUT:
                raise ConnectionTimeoutError("Timeout", self.hostname)

        else:
            try:
                self.ctrl._session = pexpect.spawn(
                    command,
                    maxread=50000,
                    searchwindowsize=None,
                    env={"TERM": "VT100"},  # to avoid color control charactes
                    echo=True  # KEEP YOUR DIRTY HANDS OFF FROM ECHO!
                )
                rows, cols = self.ctrl._session.getwinsize()
                if cols < 160:
                    self.ctrl._session.setwinsize(24, 160)
                    nrows, ncols = self.ctrl._session.getwinsize()
                    self._dbg(10, "Terminal window size changed from "
                                  "{}x{} to {}x{}".format(rows, cols, nrows, ncols))
                else:
                    self._dbg(10, "Terminal window size: {}x{}".format(rows, cols))

            except pexpect.EOF:
                raise ConnectionError("Connection error", self.hostname)
            except pexpect.TIMEOUT:
                raise ConnectionTimeoutError("Timeout", self.hostname)

            self.ctrl._session.logfile_read = self.logfile

    def connect(self):
        """
        Protocol specific implementation
        """
        raise NotImplementedError("Connection method not implemented")

    def authenticate(self):
        """
        Protocol specific implementation
        """
        raise NotImplementedError("Authentication method not implemented")

    def disconnect(self):
        """
        Protocol specific implementation
        """
        raise NotImplementedError("Authentication method not implemented")

    def try_read_prompt(self, timeout_multiplier):
        """
        based on try_read_prompt from pxssh.py
        https://github.com/pexpect/pexpect/blob/master/pexpect/pxssh.py
        """
        # maximum time allowed to read the first response
        first_char_timeout = timeout_multiplier * 2

        # maximum time allowed between subsequent characters
        inter_char_timeout = timeout_multiplier * 0.4

        # maximum time for reading the entire prompt
        total_timeout = timeout_multiplier * 4

        prompt = ""
        begin = time.time()
        expired = 0.0
        timeout = first_char_timeout

        while expired < total_timeout:
            try:
                p = self.ctrl.read_nonblocking(size=1, timeout=timeout)
                # \r=0x0d CR \n=0x0a LF
                if p not in ['\n', '\r']:  # omit the cr/lf sent to get the prompt
                    timeout = inter_char_timeout
                expired = time.time() - begin
                prompt += p
            except pexpect.TIMEOUT:
                break
            except pexpect.EOF:
                raise ConnectionError('Session disconnected')

        prompt = prompt.strip()
        return prompt

    def levenshtein_distance(self, a, b):
        """
        This calculates the Levenshtein distance between string a and b.

        :param a: String - input string a
        :param b: String - input string b
        :return: Number - Levenshtein Distance between string a and b
        """

        n, m = len(a), len(b)
        if n > m:
            a, b = b, a
            n, m = m, n
        current = range(n + 1)
        for i in range(1, m + 1):
            previous, current = current, [i] + [0] * n
            for j in range(1, n + 1):
                add, delete = previous[j] + 1, current[j - 1] + 1
                change = previous[j - 1]
                if a[j - 1] != b[i - 1]:
                    change += + 1
                current[j] = min(add, delete, change)
        return current[n]

    def detect_prompt(self, sync_multiplier=4):
        """
        This attempts to find the prompt. Basically, press enter and record
        the response; press enter again and record the response; if the two
        responses are similar then assume we are at the original prompt.
        This can be a slow function. Worst case with the default sync_multiplier
        can take 16 seconds. Low latency connections are more likely to fail
        with a low sync_multiplier. Best case sync time gets worse with a
        high sync multiplier (500 ms with default).

        """
        self.ctrl.sendline()
        self.try_read_prompt(sync_multiplier)

        attempt = 0
        max_attempts = 10
        while attempt < max_attempts:
            attempt += 1
            self._dbg(10, "Detecting prompt. Attempt ({}/{})".format(attempt, max_attempts))

            self.ctrl.sendline()
            a = self.try_read_prompt(sync_multiplier)

            self.ctrl.sendline()
            b = self.try_read_prompt(sync_multiplier)

            ld = self.levenshtein_distance(a, b)
            len_a = len(a)
            self._dbg(10, "LD={},MP={}".format(ld, sync_multiplier))
            sync_multiplier *= 1.2
            if len_a == 0:
                continue

            if float(ld) / len_a < 0.3:
                self.prompt = b.splitlines(True)[-1]
                compiled_prompt = re.compile("(\r\n|\n\r){}".format(re.escape(self.prompt)))
                self._dbg(10, "Detected prompt: '{}'".format(self.prompt))
                self.ctrl.sendline()
                self.ctrl.expect(compiled_prompt)  # match from new line
                return True

        return False

    def _acquire_password(self):
        password = self.password
        if not password:
            if self.account_manager:
                self._dbg(20,
                          "{}: {}: Acquiring password for {} from system KeyRing".format(
                              self.protocol, self.hostname, self.username))
                password = self.account_manager.get_password(self.hostname, self.username, interact=True)
                if not password:
                    self._dbg(30, "{}: {}: Password for {} does not exists in KeyRing".format(
                        self.protocol, self.hostname, self.username))
        return password

    @action
    def send_username(self, ctx):
        ctx.ctrl.sendline(self.username)
        ctx.timeout = 10
        return True

    @action
    def send_pass(self, ctx):
        password = self._acquire_password()
        if password:
            ctx.ctrl.setecho(False)
            ctx.ctrl.sendline(password)
            ctx.ctrl.setecho(True)
            ctx.timeout = 30
            return True
        else:
            self.disconnect()
            raise ConnectionAuthenticationError("Password not provided", self.hostname)

    @action
    def try_detect_prompt(self, ctx):
        ctx.finished = True
        if self.detect_prompt():
            return True
        else:
            return False

    @action
    def authentication_error(self, ctx):
        self.disconnect()
        raise ConnectionAuthenticationError("Authentication failed", self.hostname)

    @action
    def unable_to_connect(self, ctx):
        ctx.msg = "{}{}".format(self.ctrl.before, self.ctrl.after)
        return False

    @action
    def session_closed(self, ctx):
        ctx.msg = "First session closed"
        ctx.failed = True
        return False

    @action
    def send_new_line(self, ctx):
        # print(":".join("{:02x}".format(ord(c)) for c in ctx.ctrl.before))
        ctx.ctrl.send("\r\n")
        return True

    @action
    def save_pattern(self, ctx):
        self.last_pattern = ctx.pattern
        return True

    @action
    def send_q(self, ctx):
        ctx.ctrl.send("q")
        return True
