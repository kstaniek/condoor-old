# =============================================================================
#
# Copyright (c)  2015, Cisco Systems
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

import sys
import os
import re
import logging
import time

from hopinfo import make_hop_info_from_url
from controllers.pexpect_ctrl import Controller
from condoor.utils import delegate

from condoor.exceptions import ConnectionError, ConnectionTimeoutError

"""
This is a python module providing access to Cisco devices over Telnet and SSH.

"""

__version__ = '0.0.1'

__all__ = ['make_connection_from_urls', 'Connection']

supported_platforms = {
    "ASR-9000": {  # generic
                   "version": ["ASR9K"],
                   "continue": True
    },
    "ASR-9904": {
        "version": ["ASR-9904"],
        "diag_eXR": ["ASR-9904"]
    },
    "ASR-9006": {
        "version": ["ASR 9006"]
    },
    "ASR-9001": {
        "version": ["ASR-9001"]
    },
    "NCS-4000": {  # generic
                   "version": ["NCS-4000"],
                   "continue": True
    },
    "NCS-6000": {  # generic
                   "version": ["NCS-6000"],
                   "continue": True
    },
    "NCS-6008": {
        "diag_eXR": ["NCS 6008"]
    },
    "ASR-903": {
        "version": ["ASR-903"]
    },
    "ASR-901": {
        "version": ["ASR-901"]
    },
    "CRS-16": {
        "version": ["CRS-16"]
    }
}

platform_families = {
    "ASR9K": ["ASR-9000", "ASR-9001", "ASR-9006", "ASR-9904"],
    "NCS4K": ["NCS-4000"],
    "NCS6K": ["NCS-6000", "NCS-6008"],
    "ASR900": ["ASR-903", "ASR-901"],
    "CRS": ["CRS-16"]
}

drivers = {
    "ASR9K": ["ASR9K", "CRS", "NCS6K", "NCS4K"],
    "IOS": ["ASR900"],

}


def make_connection_from_urls(name, urls, platform='generic', account_manager=None, logger=None):
    if logger is None:
        logger = logging.getLogger(name)
        logger.addHandler(logging.NullHandler())

    module_str = 'condoor.platforms.%s' % platform
    try:
        __import__(module_str)
        module = sys.modules[module_str]
        driver_class = getattr(module, 'Connection')
    except ImportError:
        return None

    nodes = []
    for url in urls:
        nodes.append(make_hop_info_from_url(url))

    return driver_class(name, nodes, Controller, logger, account_manager=account_manager)


@delegate("_driver", ("reload", "send", "enable", "run_fsm"))
class Connection(object):
    """This is the main class interface for Condoor. Use this class to create
    a connection session, discover and control the remote device."""

    def __init__(self, hostname, urls, log_dir=None, log_level=logging.DEBUG, log_session=True, account_manager=None):
        """This is the constructor. The *hostname* parameter is a string representing the name of the device.
        It is used mainly for verbose logging purposes.

        The *urls* parameter represents the list of urls used to define the connection way to the
        chain of devices before reaching the target device. It allows to have single device connection
        over multiple jumphosts. For example::

            ["ssh://<username>:<password>@<host>", "telnet://<username>:<password>@<host>"]

        Currently there are two protocols supported: SSH and TELNET

        An IOS/IOS XE devices may require a privileged level password (enable password). The url parser treats
        the rest of the url (the path part + query + fragment part) as an privileged password. For example::

            ["ssh://<username>:<password>@<host>", "telnet://<username>:<password>@<host>/<enable_password>"]

        The *host* could be either the hostname or ip address.

        There could be more devices in the list which allows having multiple jumphosts.
        The last url in the list always represents the target device.


        The *log_dir* parameter contains a string representing the full path to the logging directory.
        The logging directory can store the device session log and the detailed Condoor debug log.
        If there is no *log_dir* specified the current directory is used. The possible logging levels are as follows::
        NOTSET=0
        DEBUG=10
        INFO=20
        WARN=30
        ERROR=40
        CRITICAL=50

        The default is DEBUG. If the *log_level* is set to 0 then no logging file is created.  The *log_session*
        parameters defines whether the device session log is created or not.

        """

        self._driver = None
        self._hostname = hostname
        self._urls = urls
        self._account_manager = account_manager
        self._platform = 'generic'
        self._os_type = None
        self._os_version = None
        self._family = None
        self._log_dir = log_dir
        self._log_session = log_session
        self.logger = logging.getLogger(hostname)
        self._info = {}

        if log_level > 0:
            formatter = logging.Formatter('%(asctime)-15s %(levelname)8s: %(message)s')
            if log_dir:
                # Create the log directory.
                if not os.path.exists(log_dir):
                    try:
                        os.makedirs(log_dir)
                    except IOError:
                        log_dir = "./"
                log_filename = os.path.join(log_dir, 'condoor.log')
                handler = logging.FileHandler(log_filename)

            else:
                handler = logging.StreamHandler()
                log_dir = "./"

            handler.setFormatter(formatter)
        else:
            handler = logging.NullHandler()

        self.logger.addHandler(handler)
        self.logger.setLevel(log_level)

        try:
            self._session_fd = open(os.path.join(log_dir, 'session.log'), mode="w")
        except IOError:
            self._session_fd = None

    def _set_default_log_fd(self, logfile=None):
        if self._log_session:
            if logfile is None:
                try:
                    self._session_fd = open(os.path.join(self._log_dir, 'session.log'), mode="a+")
                except IOError:
                    self._session_fd = None
            else:
                self._session_fd = logfile if isinstance(logfile, file) else None

    def discovery(self, logfile=None):
        """This method detects the device details. This method discovery the several device attributes.

        Args:
            logfile (file): Optional file descriptor for session logging. The file must be open for write.
                The session is logged only if ``log_session=True`` was passed to the constructor.
                It the parameter is not passed then the default *session.log* file is created in `log_dir`.

        """
        driver = make_connection_from_urls(self._hostname, self._urls, account_manager=self._account_manager,
                                           logger=self.logger)

        self._set_default_log_fd(logfile)

        # FIXME: Handle exceptions

        driver.connect(logfile=self._session_fd)

        show_version = driver.send("show version ")
        show_diag_xr = None

        match = re.search("Version (.*)[ |\n]", show_version)
        if match:
            self._os_version = match.group(1)

        match = re.search("(XR|XE)", show_version)
        if match:
            self._os_type = match.group(1)
        else:
            self._os_type = 'IOS'

        if self._os_type == "XR":
            match = re.search("Build Information", show_version)
            if match:
                self._os_type = "eXR"

        do_break = True
        for platform, tests in supported_platforms.iteritems():
            if "continue" in tests.keys():
                do_break = False

            for test, patterns in tests.items():
                if test == 'version':
                    for pattern in patterns:
                        match = re.search(pattern, show_version)
                        if match:
                            self._platform = platform
                            if do_break:
                                break
                            else:
                                continue
                    else:
                        continue
                    break
                if test == 'diag_eXR' and self._os_type == 'eXR':
                    if show_diag_xr is None:
                        show_diag_xr = driver.send("show diag summary")
                    for pattern in patterns:
                        match = re.search(pattern, show_diag_xr)
                        if match:
                            self._platform = platform
                            break
                    else:
                        continue
                    break
            else:
                continue
            break

        for family, platforms in platform_families.iteritems():
            if self._platform in platforms:
                self._family = family
                break

        self.logger.debug("Family: {}".format(self._family))
        self.logger.debug("Platform: {}".format(self._platform))
        self.logger.debug("OS: {}".format(self._os_type))
        self.logger.debug("Version: {}".format(self._os_version))
        self.logger.debug("Prompt: '{}'".format(driver.prompt))

        driver.disconnect()

        for driver, families in drivers.iteritems():
            if self._family in families:
                self._driver = make_connection_from_urls(self._hostname, self._urls, platform=driver,
                                                         account_manager=self._account_manager, logger=self.logger)

    def store_property(self, key, value):
        """This method stores a *value* identified by the *key* in the :class:`Connection` object.

        Args:
            key (str): Key name.
            value (object): Object to be stored

        """

        self.logger.debug("Store '{}' <- '{}'".format(key, str(value)))
        self._info[key] = value

    def get_property(self, key):
        """This method retrieves value of the *key* stored in :class:`Connection` object.
        If no value was stored for give key then None is returned

        Args:
            key (str): Key name.
        Returns:
            object|None: The stored object identified by key or None
        """

        return self._info.get(key, None)

    def connect(self, logfile=None):
        """This method connects to the device. The discovery method must be called first. If not then
        :class:`exceptions.ConnectionError` is raised

        Args:
            logfile (file): Optional file descriptor for session logging. The file must be open for write.
                The session is logged only if ``log_session=True`` was passed to the constructor.
                It the parameter is not passed then the default *session.log* file is created in `log_dir`.

        Raises:
            exceptions.ConnectionError: If the discovery method was not called first or there was a problem with getting
             the connection.
            exceptions.ConnectionAuthenticationError: If the authentication failed.
            exceptions.ConnectionTimeoutError: If the connection timeout happened.

        """

        self._set_default_log_fd(logfile)

        try:
            return self._driver.connect(logfile=self._session_fd)
        except AttributeError:
            raise ConnectionError("Platform unknown. Try detect platform first")

    def reconnect(self, max_timeout=360, logfile=None):
        """This method reconnects to the device. It can be called when after device reloads or the session was
        disconnected either by device or jumphost. If multiple jumphosts are used then `reconnect` starts from
        the last valid connection.

        Args:
            max_timeout (int): This is the maximum amount of time during the session tries to reconnect. It may take
                longer depending on the TELNET or SSH default timeout.
            logfile (file): Optional file descriptor for session logging. The file must be open for write.
                The session is logged only if ``log_session=True`` was passed to the constructor.
                It the parameter is not passed then the default *session.log* file is created in `log_dir`.

        Raises:
            exceptions.ConnectionError: If the discovery method was not called first or there was a problem with getting
             the connection.
            exceptions.ConnectionAuthenticationError: If the authentication failed.
            exceptions.ConnectionTimeoutError: If the connection timeout happened.

        """
        self._set_default_log_fd(logfile)

        begin = time.time()
        expired = 0.0
        attempt = 0
        self.logger.info("Trying to reconnect within {} seconds".format(max_timeout))
        while expired < max_timeout:
            self.logger.debug("Reconnecting. Attempt {}".format(attempt))
            try:
                self._driver.reconnect(logfile=self._session_fd)
                break
            except ConnectionError:
                expired = time.time() - begin
            except AttributeError:
                raise ConnectionError("Platform unknown. Try detect platform first")
            attempt += 1
        else:
            self.logger.error("Unable to reconnect")
            raise ConnectionTimeoutError("Unable to reconnect to device within {} s".format(max_timeout))

    def disconnect(self):
        """
        This method disconnect the session from the device and all the jumphosts in the path.
        """
        try:
            self._driver.disconnect()
        except AttributeError:
            pass
        finally:
            if self._session_fd:
                self._session_fd.close()

    @property
    def platform(self):
        if self._platform == 'generic':
            self.detect_platform()
        return self._platform

    @platform.setter
    def platform(self, platform):
        self._platform = platform

    @property
    def family(self):
        if self._family == 'generic':
            self.detect_platform()
        return self._family

    @property
    def prompt(self):
        try:
            return self._driver.prompt
        except AttributeError:
            return None

    @property
    def os_type(self):
        try:
            return self._os_type
        except AttributeError:
            return 'unknown'

    @property
    def hostname(self):
        try:
            return self._hostname
        except AttributeError:
            return "host"

    @property
    def is_connected(self):
        try:
            return self._driver.is_connected
        except AttributeError:
            return False
