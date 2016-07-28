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
#import logging


class NCS5500Handler(XRHandler):
    platform = "NCS5500"

    def finish(self):
        print("FINISH")


class TestNCS5500Connection(TestCase):

    def setUp(self):
        self.server = TelnetServer(("127.0.0.1", 10023), NCS5500Handler)
        self.server_thread = Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()

        self.log_session = False
        self.logfile_condoor = None  # sys.stderr
        self.log_level = 20


    def tearDown(self):
        self.conn.disconnect()

        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join()

    def test_NCS5500_1_discovery(self):
        urls = ["telnet://admin:admin@127.0.0.1:10023"]
        conn = condoor.Connection("host", urls, log_session=self.log_session, log_level=self.log_level)
        self.conn = conn
        conn.connect(self.logfile_condoor)

        self.assertEqual(conn.hostname, "ios", "Wrong Hostname: {}".format(conn.hostname))
        self.assertEqual(conn.family, "NCS5500", "Wrong Family: {}".format(conn.family))
        self.assertEqual(conn.platform, "NCS-5508", "Wrong Platform: {}".format(conn.platform))
        self.assertEqual(conn.os_type, "eXR", "Wrong OS Type: {}".format(conn.os_type))
        self.assertEqual(conn.os_version, "6.0.1", "Wrong Version: {}".format(conn.os_version))
        self.assertEqual(conn.udi['name'], "Rack 0", "Wrong Name: {}".format(conn.udi['name']))
        self.assertEqual(conn.udi['description'], "NCS5500 8 Slot Single Chassis",
                         "Wrong Description: {}".format(conn.udi['description']))
        self.assertEqual(conn.udi['pid'], "NCS-5508", "Wrong PID: {}".format(conn.udi['pid']))
        self.assertEqual(conn.udi['vid'], "V01", "Wrong VID: {}".format(conn.udi['vid']))
        self.assertEqual(conn.udi['sn'], "FGE194714QX", "Wrong S/N: {}".format(conn.udi['sn']))
        self.assertEqual(conn.prompt, "6.0.1", "Wrong Prompt: {}".format(conn.prompt))

        # self.logger.info("Hostname: '{}'".format(self.hostname))
        # self.logger.info("Family: {}".format(self.family))
        # self.logger.info("Platform: {}".format(self.platform))
        # self.logger.info("OS: {}".format(os_names[self.os_type]))
        # self.logger.info("Version: {}".format(self.os_version))
        # self.logger.info("Name: {}".format(self.udi['name']))
        # self.logger.info("Description: {}".format(self.udi['description']))
        # self.logger.info("PID: {}".format(self.udi['pid']))
        # self.logger.info("VID: {}".format(self.udi['vid']))
        # self.logger.info("SN: {}".format(self.udi['sn']))
        # self.logger.info("Prompt: '{}'".format(self._prompt))
        # self.logger.info("Is connected to console: {}".format(self.is_console))
        # self._discovered = True


    def test_NCS5500_2_connection_wrong_user(self):
        urls = ["telnet://root:admin@127.0.0.1:10023"]
        conn = condoor.Connection("host", urls, log_session=self.log_session, log_level=self.log_level)
        with self.assertRaises(condoor.ConnectionError):
            conn.connect(self.logfile_condoor)

    def test_NCS5500_3_connection_refused(self):
        urls = ["telnet://admin:admin@127.0.0.1:10024"]
        conn = condoor.Connection("host", urls, log_session=self.log_session,  log_level=self.log_level)
        with self.assertRaises(condoor.ConnectionError):
            conn.connect(self.logfile_condoor)


