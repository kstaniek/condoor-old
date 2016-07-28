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


class TestNCS5500Connection(TestCase):

    def setUp(self):
        self.server = TelnetServer(("127.0.0.1", 10023), NCS5500Handler)
        self.server_thread = Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()

        self.log_session = False
        self.logfile_condoor = None  # sys.stderr
        self.log_level = 10


    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join()

    def test_NCS5500_1_discovery(self):
        urls = ["telnet://admin:admin@127.0.0.1:10023"]
        conn = condoor.Connection("host", urls, log_session=self.log_session, log_level=self.log_level)
        conn.connect(self.logfile_condoor)

        self.assertEqual(conn.hostname, "ios", "Hostname")
        self.assertEqual(conn.family, "ios", "Family")
        self.assertEqual(conn.platform, "ios", "Platform")
        self.assertEqual(conn.os_type, "ios", "OS")
        self.assertEqual(conn.version, "6.0.1", "Version")
        self.assertEqual(conn.udi['name'], "6.0.1", "Name")
        self.assertEqual(conn.udi['description'], "6.0.1", "Description")
        self.assertEqual(conn.udi['pid'], "6.0.1", "PID")
        self.assertEqual(conn.udi['vid'], "6.0.1", "VID")
        self.assertEqual(conn.udi['sn'], "6.0.1", "S/N")
        self.assertEqual(conn._prompt, "6.0.1", "Prompt")

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


        conn.disconnect()

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


