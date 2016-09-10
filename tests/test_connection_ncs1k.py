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

from xrmock.xrmock import TelnetServer, XRHandler
from threading import Thread

import condoor


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
        self.server_thread.setDaemon(True)
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

    def test_NCS1K_1_discovery(self):

        urls = ["telnet://admin:admin@127.0.0.1:10023"]
        conn = condoor.Connection("host", urls, log_session=self.log_session, log_level=self.log_level)
        self.conn = conn
        conn.discovery(self.logfile_condoor)

        self.assertEqual(conn._discovered, True, "Not discovered properly")
        self.assertEqual(conn.hostname, "ios", "Wrong Hostname: {}".format(conn.hostname))
        self.assertEqual(conn.family, "NCS1K", "Wrong Family: {}".format(conn.family))
        self.assertEqual(conn.platform, "NCS1002", "Wrong Platform: {}".format(conn.platform))
        self.assertEqual(conn.os_type, "eXR", "Wrong OS Type: {}".format(conn.os_type))
        self.assertEqual(conn.os_version, "6.0.1", "Wrong Version: {}".format(conn.os_version))
        self.assertEqual(conn.udi['name'], "Rack 0", "Wrong Name: {}".format(conn.udi['name']))
        self.assertEqual(conn.udi['description'], "Network Convergence System 1000 Controller",
                         "Wrong Description: {}".format(conn.udi['description']))
        self.assertEqual(conn.udi['pid'], "NCS1002", "Wrong PID: {}".format(conn.udi['pid']))
        self.assertEqual(conn.udi['vid'], "V01", "Wrong VID: {}".format(conn.udi['vid']))
        self.assertEqual(conn.udi['sn'], "CHANGE-ME-", "Wrong S/N: {}".format(conn.udi['sn']))
        self.assertEqual(conn.prompt, "RP/0/RP0/CPU0:ios#", "Wrong Prompt: {}".format(conn.prompt))
        conn.disconnect()

    def test_NCS1K_2_connection_refused(self):
        urls = ["telnet://admin:admin@127.0.0.1:10024"]
        self.conn = condoor.Connection("host", urls, log_session=self.log_session, log_level=0)
        with self.assertRaises(condoor.ConnectionError):
            self.conn.discovery(self.logfile_condoor)

    def test_NCS1K_3_connection_wrong_user(self):
        urls = ["telnet://root:admin@127.0.0.1:10023"]
        self.conn = condoor.Connection("host", urls, log_session=self.log_session, log_level=0)
        with self.assertRaises(condoor.ConnectionError):
            self.conn.discovery(self.logfile_condoor)
