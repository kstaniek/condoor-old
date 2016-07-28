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


from unittest import TestCase

from xrmock.xrmock import TelnetServer, XRHandler
from threading import Thread

import condoor
import sys


class NCS1KHandler(XRHandler):
    platform = "NCS1K"
    response_dict = {
        'show_install_request': "10.77.132.127: Permission denied"
    }
    action_dict = {
        'show_install_request': {'AFTER': 'disconnect'}
    }

    def disconnect(self):
        self.RUNSHELL = False


class TestNCS1KConnection(TestCase):

    def setUp(self):
        self.server = TelnetServer(("127.0.0.1", 10023), NCS1KHandler)
        self.server_thread = Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        self.log_session = False
        self.logfile_condoor = None  # sys.stderr
        self.log_level = 0

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join()

    def test_NCS1K_1_discovery(self):

        urls = ["telnet://admin:admin@127.0.0.1:10023"]
        conn = condoor.Connection("host", urls, log_session=self.log_session, log_level=0)
        conn.discovery(self.logfile_condoor)
        conn.disconnect()

    def test_NCS1K_2_connection_refused(self):
        urls = ["telnet://admin:admin@127.0.0.1:10024"]
        conn = condoor.Connection("host", urls, log_session=self.log_session, log_level=0)
        with self.assertRaises(condoor.ConnectionError):
            conn.discovery(self.logfile_condoor)

    def test_NCS1K_3_connection_wrong_user(self):
        urls = ["telnet://root:admin@127.0.0.1:10023"]
        conn = condoor.Connection("host", urls, log_session=self.log_session, log_level=0)
        with self.assertRaises(condoor.ConnectionError):
            conn.discovery(self.logfile_condoor)

