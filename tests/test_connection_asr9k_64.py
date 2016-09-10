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
import os


class ASR9K64Handler(XRHandler):
    platform = "ASR9K-64"


class TestASR9K64Connection(TestCase):

    def setUp(self):
        self.server = TelnetServer(("127.0.0.1", 10023), ASR9K64Handler)
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
        self.conn.disconnect()
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join()

    def test_ASR9K64_1_discovery(self):
        urls = ["telnet://admin:admin@127.0.0.1:10023"]
        conn = condoor.Connection("host", urls, log_session=self.log_session, log_level=self.log_level)
        self.conn = conn
        conn.connect(self.logfile_condoor)

        self.assertEqual(conn._discovered, True, "Not discovered properly")
        self.assertEqual(conn.hostname, "ios", "Wrong Hostname: {}".format(conn.hostname))
        self.assertEqual(conn.family, "ASR9K", "Wrong Family: {}".format(conn.family))
        self.assertEqual(conn.platform, "ASR-9904", "Wrong Platform: {}".format(conn.platform))
        self.assertEqual(conn.os_type, "eXR", "Wrong OS Type: {}".format(conn.os_type))
        self.assertEqual(conn.os_version, "6.2.1.11I", "Wrong Version: {}".format(conn.os_version))
        self.assertEqual(conn.udi['name'], "Rack 0", "Wrong Name: {}".format(conn.udi['name']))
        self.assertEqual(conn.udi['description'], "ASR-9904 AC Chassis",
                         "Wrong Description: {}".format(conn.udi['description']))
        self.assertEqual(conn.udi['pid'], "ASR-9904-AC", "Wrong PID: {}".format(conn.udi['pid']))
        self.assertEqual(conn.udi['vid'], "V01", "Wrong VID: {}".format(conn.udi['vid']))
        self.assertEqual(conn.udi['sn'], "FOX1739G95R", "Wrong S/N: {}".format(conn.udi['sn']))
        self.assertEqual(conn.prompt, "RP/0/RP0/CPU0:ios#", "Wrong Prompt: {}".format(conn.prompt))

    def test_ASR9K64_2_connection_wrong_user(self):
        urls = ["telnet://root:admin@127.0.0.1:10023"]
        self.conn = condoor.Connection("host", urls, log_session=self.log_session, log_level=self.log_level)

        with self.assertRaises(condoor.ConnectionError):
            self.conn.connect(self.logfile_condoor)

    def test_ASR9K64_3_connection_refused(self):
        urls = ["telnet://admin:admin@127.0.0.1:10024"]
        self.conn = condoor.Connection("host", urls, log_session=self.log_session, log_level=self.log_level)
        with self.assertRaises(condoor.ConnectionError):
            self.conn.connect(self.logfile_condoor)


if __name__ == '__main__':
    from unittest import main
    main()
