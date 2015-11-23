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
from functools import wraps

from hopinfo import make_hop_info_from_url
from controllers.pexpect_ctrl import Controller
from condoor.utils import delegate

from pexpect import TIMEOUT
from condoor.controllers.fsm import FSM, action

from condoor.exceptions import CommandTimeoutError, ConnectionError, ConnectionTimeoutError, CommandError, \
    CommandSyntaxError, ConnectionAuthenticationError, GeneralError, InvalidHopInfoError

"""
This is a python module providing access to Cisco devices over Telnet and SSH.

"""

__all__ = ['make_connection_from_urls', 'Connection', 'FSM', 'TIMEOUT', 'action',
           'CommandTimeoutError', 'ConnectionError', 'ConnectionTimeoutError', 'CommandError',
           'CommandSyntaxError', 'ConnectionAuthenticationError']

supported_platforms = {
    "ASR-9000": {  # generic
                   "version": ["ASR9K "],
                   "continue": True
    },
    "ASR-9904": {
        "version": ["ASR-9904 "],
        "diag_eXR": ["ASR-9904 "]
    },
    "ASR-9010": {
        "version": ["ASR 9010 ", "ASR-9010 "]  # yes, we've got two different chassis ID for the same platform
    },
    "ASR-9006": {
        "version": ["ASR 9006 "]
    },
    "ASR-9001": {
        "version": ["ASR-9001 "]
    },
    "NCS-4000": {  # generic
                   "version": ["NCS-4000 "],
                   "continue": True
    },
    "NCS-6000": {  # generic
                   "version": ["NCS-6000 "],
                   "continue": True
    },
    "NCS-6008": {
        "diag_eXR": ["NCS 6008 "]
    },
    "ASR-903": {
        "version": ["ASR-903 "]
    },
    "ASR-901": {
        "version": ["ASR-901 "]
    },
    "CRS": {
        "version": ["CRS"],
        "continue": True
    },
    "CRS-16": {
        "version": ["CRS-16 ", "CRS 16 "]
    }
}

platform_families = {
    "ASR9K": ["ASR-9000", "ASR-9904", "ASR-9010", "ASR-9006", "ASR-9001"],
    "NCS4K": ["NCS-4000"],
    "NCS6K": ["NCS-6000", "NCS-6008"],
    "ASR900": ["ASR-903", "ASR-901"],
    "CRS": ["CRS", "CRS-16"]
}

drivers = {
    "ASR9K": ["ASR9K", "CRS", "NCS6K", "NCS4K"],
    "IOS": ["ASR900"],
    "generic": ["generic"]

}

# def make_connection_from_urls(name, urls, platform='generic', account_manager=None, logger=None):
#     if logger is None:
#         logger = logging.getLogger(name)
#         logger.addHandler(logging.NullHandler())
#
#     module_str = 'condoor.platforms.%s' % platform
#     try:
#         __import__(module_str)
#         module = sys.modules[module_str]
#         driver_class = getattr(module, 'Connection')
#     except ImportError:
#         raise GeneralError("Platform {} not supported".format(platform))
#
#     return driver_class(name, nodes, Controller, logger, account_manager=account_manager)


@delegate("_driver", ("reload", "send", "enable", "run_fsm"))
class Connection(object):
    """This is the main class interface for Condoor. Use this class to create
    a connection session, discover and control the remote device."""

    def __init__(self, name, urls, log_dir=None, log_level=logging.DEBUG, log_session=True, account_manager=None):
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
        self._name = name
        self._hostname = name

        # normalise the urls to the list of the lists of str (for multiple console connections to the device)
        if isinstance(urls, list):
            if urls:
                if isinstance(urls[0], list):
                    # multiple connections (list of the lists)
                    self._urls = urls
                elif isinstance(urls[0], str):
                    # single connections (make it list of the lists)
                    self._urls = [urls]
            else:
                raise GeneralError("No target host url provided.")
        elif isinstance(urls, str):
            self._urls = [[urls]]

        nodes = []
        for index, target in enumerate(self._urls):
            nodes.insert(index, list())
            for url in target:
                nodes[index].append(make_hop_info_from_url(url))
        self._nodes = nodes
        self._last_driver_index = 0

        self._account_manager = account_manager
        self._platform = 'generic'
        self._os_type = None
        self._os_version = None
        self._family = None
        self._prompt = None
        self._log_dir = log_dir
        self._log_session = log_session
        self.logger = logging.getLogger('condoor')
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
                except (IOError, AttributeError):
                    self._session_fd = None
            else:
                self._session_fd = logfile if isinstance(logfile, file) else None

    def _init_driver(self, driver_name=None):
        if driver_name is None:
            for driver_name, families in drivers.iteritems():
                if self._family in families:
                    break
            else:
                driver_name = 'generic'

        module_str = 'condoor.platforms.%s' % driver_name
        try:
            __import__(module_str)
            module = sys.modules[module_str]
            driver_class = getattr(module, 'Connection')
        except ImportError:
            raise GeneralError("Platform {} not supported".format(self._platform))

        driver = driver_class(
            self._hostname,
            self._nodes[self._last_driver_index],
            Controller,
            self.logger,
            account_manager=self._account_manager
        )
        self._driver = driver

    def _shift_driver(self):
        no_hosts = len(self._nodes)
        del self._driver
        self._last_driver_index += 1
        if self._last_driver_index >= no_hosts:
            self._last_driver_index = 0

        self._init_driver()

    def discovery(self, logfile=None):
        """This method detects the device details. This method discovery the several device attributes.

        Args:
            logfile (file): Optional file descriptor for session logging. The file must be open for write.
                The session is logged only if ``log_session=True`` was passed to the constructor.
                It the parameter is not passed then the default *session.log* file is created in `log_dir`.

        """

        self._set_default_log_fd(logfile)

        self._init_driver()

        no_hosts = len(self._nodes)
        for i in xrange(no_hosts):
            try:
                self._driver.connect(logfile=self._session_fd)
                break
            except ConnectionError:
                self._shift_driver()
        else:
            raise ConnectionError("Unable to connect to the device")

        try:
            show_version = self._driver.send("show version brief", timeout=120)
        except CommandError:
            # IOS Hack - need to check if show version brief is supported on IOS/IOSXE
            show_version = self._driver.send("show version", timeout=120)

        self.logger.debug("show version: \n{}".format(show_version))
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
                        show_diag_xr = self._driver.send("show diag summary")
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

        self.logger.debug("Platform string: {}".format(self._platform))

        self._prompt = self._driver.prompt
        self._driver.disconnect()

        for family, platforms in platform_families.iteritems():
            if self._platform in platforms:
                self._family = family
                break
        else:
            self._family = 'generic'
            raise GeneralError("Platform unsupported. Please provide show version to author")

        # getting the new driver based on detected device family
        self._init_driver()
        self._driver.determine_hostname(self._prompt)

        self._hostname = self._driver.hostname

        self.logger.info("Hostname: '{}'".format(self.hostname))
        self.logger.info("Family: {}".format(self.family))
        self.logger.info("Platform: {}".format(self.platform))
        self.logger.info("OS: {}".format(self.os_type))
        self.logger.info("Version: {}".format(self.os_version))
        self.logger.info("Prompt: '{}'".format(self._prompt))


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
        :class:`ConnectionError` is raised

        Args:
            logfile (file): Optional file descriptor for session logging. The file must be open for write.
                The session is logged only if ``log_session=True`` was passed to the constructor.
                It the parameter is not passed then the default *session.log* file is created in `log_dir`.

        Raises:
            ConnectionError: If the discovery method was not called first or there was a problem with getting
             the connection.
            ConnectionAuthenticationError: If the authentication failed.
            ConnectionTimeoutError: If the connection timeout happened.

        """
        self._set_default_log_fd(logfile)
        self._init_driver()
        no_hosts = len(self._nodes)
        result = False
        for i in xrange(no_hosts):
            try:
                result = self._driver.connect(logfile=self._session_fd)
                break
            except ConnectionError as e:
                # if this is last try raise the exception
                if (i + 1) == no_hosts:
                    raise e
                else:
                    self._shift_driver()
            except AttributeError:
                raise ConnectionError("Platform unknown. Try detect platform first")

        else:
            # This will never be executed
            raise ConnectionError("Unable to connect to the device")

        return result

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
            ConnectionError: If the discovery method was not called first or there was a problem with getting
             the connection.
            ConnectionAuthenticationError: If the authentication failed.
            ConnectionTimeoutError: If the connection timeout happened.

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
                self._shift_driver()
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
        """Returns the string representing hardware platform model. For example: ASR-9010, ASR922, NCS-4006, etc."""
        if self._platform == 'generic':
            self.discovery()
        return self._platform

    @platform.setter
    def platform(self, platform):
        self._platform = platform

    @property
    def family(self):
        """Returns the string representing hardware platform family. For example: ASR9K, ASR900, NCS6K, etc."""
        if self._family == 'generic':
            self.discovery()
        return self._family

    @property
    def prompt(self):
        """Returns the target device prompt if detected or *None*."""
        try:
            return self._driver.prompt
        except AttributeError:
            return None

    @property
    def os_type(self):
        """Returns the string representing the Operating System type. For example: IOS, XR, eXR. If not detected returns
        *None*"""
        try:
            return self._os_type
        except AttributeError:
            return None

    @property
    def os_version(self):
        """Returns the string representing the Operating System version. For example 5.3.1.
        If not detected returns *None*"""
        try:
            return self._os_version
        except AttributeError:
            return None

    @property
    def hostname(self):
        """Returns the string representing the target device hostname"""
        try:
            return self._hostname
        except AttributeError:
            return "host"

    @property
    def is_connected(self):
        """Returns boolean value. *True* if target device is connected, *False* if not connected"""
        try:
            return self._driver.is_connected
        except AttributeError:
            return False
