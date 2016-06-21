# =============================================================================
# controllers
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

import logging

from time import sleep

from ..utils import to_list
from ..utils import delegate

from ..controllers.protocols import make_protocol
from ..exceptions import ConnectionError, ConnectionTimeoutError

import pexpect


# Delegate following methods to _session class
@delegate("_session", ("expect", "expect_exact", "sendline",
                       "isalive", "sendcontrol", "send", "read_nonblocking", "setecho"))
class Controller(object):
    def __init__(self, platform, hostname, hosts, account_manager=None, max_attempts=1, logfile=None):
        self.hosts = to_list(hosts)
        self.max_attempts = max_attempts
        self.account_mgr = account_manager
        self.session_log = logfile
        self.hostname = hostname
        self.platform = platform
        self.connected = False
        self.authenticated = False
        self._session = None
        self.detected_prompts = []
        self.is_target = False
        self.last_hop = 0
        self.last_pattern = None
        self.logger = logging.getLogger("condoor.controller")
        self._clear_detected_prompts()

    @property
    def before(self):
        """
        Property added to imitate pexpect.spawn class
        """
        return self._session.before if self._session else None

    @property
    def after(self):
        """
        Property added to imitate pexpect.spawn class
        """
        return self._session.after if self._session else None

    @property
    def detected_target_prompt(self):
        """
        Detected target device prompt detected by controller
        """
        return self.detected_prompts[-1] if len(self.hosts) > 0 else ""

    @detected_target_prompt.setter
    def detected_target_prompt(self, prompt):
        target_hop = len(self.hosts)
        self._dbg(10, "[{}] {}: Updated target prompt: {}".format(target_hop, self.hosts[-1].hostname, prompt))
        self.detected_prompts[-1] = prompt

    def connect(self, start_hop=0, spawn=True, detect_prompt=True):
        # it can restart from the last hop.

        connected = self.connected
        if connected:
            spawn = False

        if self.last_hop > 0 and start_hop == 0:
            start_hop = self.last_hop

        hosts = self.hosts[self.last_hop:]
        host_count = len(hosts)

        self._dbg(10, "Restarting from hop: {}".format(start_hop))

        for hop, host in enumerate(hosts, start=start_hop+1):
            if hop == host_count:
                self.is_target = True

            if not host.is_valid():
                raise ConnectionError("Invalid host", host)
            attempt = 1
            while attempt <= self.max_attempts:
                if not host.is_reachable():
                    self._dbg(40, "[{}] {}: Host not reachable".format(hop, host.hostname))
                else:
                    self._dbg(
                        10,
                        "[{}] {}: Connecting. Attempt ({}/{})".format(hop, host.hostname, attempt, self.max_attempts)
                    )
                    try:
                        if self.is_target:
                            self._dbg(10, "[{}] {}: Connecting to target device".format(hop, host.hostname))
                        else:
                            self._dbg(10, "[{}] {}: Connecting to jump host".format(hop, host.hostname))

                        protocol = make_protocol(self, host, spawn, self.account_mgr, self.session_log)
                        if protocol.connect():
                            if protocol.authenticate(self.detected_prompts[hop]):
                                connected = True
                                if detect_prompt:
                                    if not protocol.detect_prompt():
                                        connected = False
                        else:
                            connected = False
                    except ConnectionTimeoutError as e:
                        self._dbg(40, "Error during connecting to device: {}".format(e.message))
                        self.disconnect()
                        raise
                    except Exception as e:
                        self._dbg(40, "Error during connecting to device: {}".format(e.message))
                        raise

                    if connected:
                        self.detected_prompts[hop] = protocol.prompt
                        break

                attempt += 1
                sleep(2)
            else:
                self._dbg(40, "[{}] {}: Connection error. ""Max attempts reached.".format(hop, host.hostname))
                self.disconnect()
                raise ConnectionError(host=self.hostname)

            self._dbg(10, "[{}] {}: Connected successfully".format(hop, host.hostname))

        if connected:
            self._dbg(10, "Connected target device")
            self.connected = True

        return connected

    def disconnect(self):
        """
        Gracefully disconnect from all the nodes
        """
        self._dbg(10, "Initializing the disconnection process")
        if self._session and self.isalive():
            self._dbg(10, "Disconnecting the sessions")
            index = 0
            hop = 0
            while index != 1 and hop < 10:
                self.sendline('exit')
                index = self.expect(
                    [pexpect.TIMEOUT, pexpect.EOF, "con.*is now available|rommon|User Access Verification"],
                    timeout=2
                )
                if index == 1:
                    break

                if index == 2:  # console connected through TS
                    self._dbg(10, "Console connection detected")
                    self.sendline('\x03')
                    self.sendcontrol(']')
                    self.sendline('quit')

                hop += 1

        self._session.close()
        self._dbg(10, "Disconnected")
        self.last_hop = 0
        self.last_pattern = None
        self.connected = False

    def _dbg(self, level, msg):
        self.logger.log(level, "[{}]: [CTRL] {}".format(self.hostname, msg))

    def _clear_detected_prompts(self):
        self.detected_prompts = []
        for i in xrange(len(self.hosts) + 1):
            self.detected_prompts.append(None)
        self.detected_prompts[0] = "FaKePrOmPt"