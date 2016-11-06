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

from tests.dmock.dmock import TelnetServer, ASR901Handler
from threading import Thread

import condoor
import os


class TestASR901Connection(TestCase):

    def setUp(self):
        self.server = TelnetServer(("127.0.0.1", 10025), ASR901Handler)
        self.server_thread = Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()

        debug = os.getenv("TEST_DEBUG", None)
        if debug:
            self.log_session = True
            import sys
            self.logfile_condoor = sys.stderr
            self.log_level = 10

        else:
            self.log_session = False
            self.logfile_condoor = None  # sys.stderr
            self.log_level = 0

    def tearDown(self):
        # Disconnect to make sure the server finishes the current request
        if self.conn.is_connected:
            self.conn.disconnect()
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join()

    def test_ASR901_1_discovery(self):
        """ASR901: Test the connection and discovery"""

        try:
            os.remove('/tmp/condoor.shelve')
        except OSError:
            pass

        urls = ["telnet://admin:admin@127.0.0.1:10025/admin"]
        conn = condoor.Connection("host", urls, log_session=self.log_session, log_level=self.log_level)
        self.conn = conn
        conn.connect(self.logfile_condoor)

        self.assertEqual(conn._discovered, True, "Not discovered properly")
        self.assertEqual(conn.hostname, "CSG-1202-ASR901", "Wrong Hostname: {}".format(conn.hostname))
        self.assertEqual(conn.family, "ASR900", "Wrong Family: {}".format(conn.family))
        self.assertEqual(conn.platform, "A901", "Wrong Platform: {}".format(conn.platform))
        self.assertEqual(conn.os_type, "IOS", "Wrong OS Type: {}".format(conn.os_type))
        self.assertEqual(conn.os_version, "15.3(2)S1", "Wrong Version: {}".format(conn.os_version))
        self.assertEqual(conn.udi['name'], "A901-6CZ-FT-A Chassis", "Wrong Name: {}".format(conn.udi['name']))
        self.assertEqual(conn.udi['description'], "A901-6CZ-FT-A Chassis",
                         "Wrong Description: {}".format(conn.udi['description']))
        self.assertEqual(conn.udi['pid'], "A901-6CZ-FT-A", "Wrong PID: {}".format(conn.udi['pid']))
        self.assertEqual(conn.udi['vid'], "V01", "Wrong VID: {}".format(conn.udi['vid']))
        self.assertEqual(conn.udi['sn'], "CAT1650U01P", "Wrong S/N: {}".format(conn.udi['sn']))
        self.assertEqual(conn.prompt, "CSG-1202-ASR901>", "Wrong Prompt: {}".format(conn.prompt))
        with self.assertRaises(condoor.CommandSyntaxError):
            conn.send("wrongcommand")

        conn.disconnect()

    def test_ASR901_2_discovery(self):
        """ASR901: Test whether the cached information is used"""
        urls = ["telnet://admin:admin@127.0.0.1:10025/admin"]
        conn = condoor.Connection("host", urls, log_session=self.log_session, log_level=self.log_level)
        self.conn = conn
        conn.connect(self.logfile_condoor)

        self.assertEqual(conn._discovered, True, "Not discovered properly")
        self.assertEqual(conn.hostname, "CSG-1202-ASR901", "Wrong Hostname: {}".format(conn.hostname))
        self.assertEqual(conn.family, "ASR900", "Wrong Family: {}".format(conn.family))
        self.assertEqual(conn.platform, "A901", "Wrong Platform: {}".format(conn.platform))
        self.assertEqual(conn.os_type, "IOS", "Wrong OS Type: {}".format(conn.os_type))
        self.assertEqual(conn.os_version, "15.3(2)S1", "Wrong Version: {}".format(conn.os_version))
        self.assertEqual(conn.udi['name'], "A901-6CZ-FT-A Chassis", "Wrong Name: {}".format(conn.udi['name']))
        self.assertEqual(conn.udi['description'], "A901-6CZ-FT-A Chassis",
                         "Wrong Description: {}".format(conn.udi['description']))
        self.assertEqual(conn.udi['pid'], "A901-6CZ-FT-A", "Wrong PID: {}".format(conn.udi['pid']))
        self.assertEqual(conn.udi['vid'], "V01", "Wrong VID: {}".format(conn.udi['vid']))
        self.assertEqual(conn.udi['sn'], "CAT1650U01P", "Wrong S/N: {}".format(conn.udi['sn']))
        self.assertEqual(conn.prompt, "CSG-1202-ASR901>", "Wrong Prompt: {}".format(conn.prompt))
        with self.assertRaises(condoor.CommandSyntaxError):
            conn.send("wrongcommand")

        conn.disconnect()

    def test_ASR901_3_connection_wrong_password(self):
        """ASR901: Test wrong password"""
        urls = ["telnet://:password@127.0.0.1:10025/admin"]
        self.conn = condoor.Connection("host", urls, log_session=self.log_session, log_level=self.log_level)

        with self.assertRaises(condoor.ConnectionAuthenticationError):
            self.conn.connect(self.logfile_condoor)

    def test_ASR901_4_connection_wrong_enable_password(self):
        """ASR901: Test wrong enable password"""
        urls = ["telnet://:password@127.0.0.1:10025/admin"]
        self.conn = condoor.Connection("host", urls, log_session=self.log_session, log_level=self.log_level)

        with self.assertRaises(condoor.ConnectionAuthenticationError):
            self.conn.connect(self.logfile_condoor)


if __name__ == '__main__':
    from unittest import main
    main()
