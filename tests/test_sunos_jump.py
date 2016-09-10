# =============================================================================
#
# Copyright (c) 2016, Cisco Systems
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

import os
from unittest import TestCase

from xrmock.xrmock import TelnetServer, TelnetHandler, command
from threading import Thread

import condoor


class SunHandler(TelnetHandler):
    PROMPT = "TEST "  # Intentionally wierd prompt
    WELCOME = "Last login: Wed Jul 27 00:44:30 from localhost"

    authNeedUser = True
    authNeedPass = True
    response_dict = {}
    action_dict = {}
    username = "admin"
    password = "admin"
    PROMPT_USER = "login:"
    PROMPT_PASS = "This is your AD password:"

    def authCallback(self, username, password):
        if password != self.password:
            raise Exception()
        return True

    def authentication_ok(self):
        username = None
        password = None
        for _ in range(1):
            if self.authCallback:

                if self.authNeedPass:
                    password = self.readline(echo=False, prompt=self.PROMPT_PASS, use_history=False)
                    if password == 'QUIT':
                        self.RUNSHELL = False
                        return True

                    if self.DOECHO:
                        self.write("\n")
                try:
                    self.authCallback(None, password)
                except:
                    self.username = None
                    continue

                else:
                    # Successful authentication
                    self.username = username
                    return True
            else:
                # No authentication desired
                self.username = None
                return True
        else:
            self.writeresponse("Login incorrect")
            return False

    @command('telnet')
    def telnet(self, params):
        self.writeresponse("""Trying host1...
Connected to host1.
Escape character is '^]'.""")


class TestSunConnection(TestCase):
    def setUp(self):
        self.server = TelnetServer(("127.0.0.1", 10023), SunHandler)
        self.server_thread = Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        self.log_session = False
        self.logfile_condoor = None  # sys.stderr
        self.log_level = 0

        try:
            os.remove('/tmp/condoor.shelve')
        except:
            pass

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join()

    def test_sun_connection(self):
        urls = ["telnet://admin:admin@127.0.0.1:10023", "telnet://admin:admin@host1"]
        conn = condoor.Connection("host", urls, log_session=self.log_session, log_level=self.log_level)

        with self.assertRaises(condoor.ConnectionTimeoutError):
            conn.connect(self.logfile_condoor)

    def test_sun_connection_wrong_passowrd(self):
        urls = ["telnet://admin:wrong@127.0.0.1:10023", "telnet://admin:admin@host1"]
        conn = condoor.Connection("host", urls, log_session=self.log_session, log_level=self.log_level)

        with self.assertRaises(condoor.ConnectionAuthenticationError):
            conn.connect(self.logfile_condoor)
