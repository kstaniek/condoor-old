# =============================================================================
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

import sys
import os
import re
import logging
import time
import shelve
import hashlib

from hopinfo import make_hop_info_from_url
from controllers.pexpect_ctrl import Controller
from condoor.utils import delegate, FilteredFileHandler, FilteredFile
from condoor.patterns import YPatternManager

from pexpect import TIMEOUT
from condoor.controllers.fsm import FSM, action

from condoor.exceptions import ConnectionError, ConnectionTimeoutError, CommandError, \
    CommandSyntaxError, ConnectionAuthenticationError, GeneralError

__version__ = '1.0.0'

"""
This is a python module providing access to Cisco devices over Telnet and SSH.

"""

__all__ = ['Connection', 'FSM', 'TIMEOUT', 'action', 'pattern_manager'
           'CommandTimeoutError', 'ConnectionError', 'ConnectionTimeoutError', 'CommandError',
           'CommandSyntaxError', 'ConnectionAuthenticationError']

_cache_file = "/tmp/condoor.shelve"

drivers = {
    "XR": ["ASR9K", "CRS", "NCS6K", "NCS4K", "CRS", "NCS5K", "NCS5500"],
    "IOS": ["ASR900"],
    "NX-OS": ["N9K"],
    "generic": ["generic"]

}

os_names = {
    'IOS': 'IOS',
    'XR': 'IOS XR',
    'eXR': 'IOS XR 64 bit',
    'XE': 'IOS XE',
    'NX-OS': 'NX-OS',
    'Calvados': 'IOS XR Admin'
}

""" This is a global pattern manager to provide RegExp patterns for various platform and usecases.
It can be used in plugins if common platform specific pattern is needed"""
pattern_manager = YPatternManager()


@delegate("_driver", ("reload", "send", "enable", "run_fsm", "send_xml"))
class Connection(object):
    """This is the main class interface for Condoor. Use this class to create
    a connection session, discover and control the remote device."""

    def __init__(self, name, urls, log_dir=None, log_level=logging.DEBUG, log_session=True, account_manager=None):
        """This is the constructor. The *hostname* parameter is a string representing the name of the device.
        It is used mainly for verbose logging purposes.

        The *urls* parameter represents the list of urls used to define the connection way to the
        chain of devices before reaching the target device. It allows to have single device connection
        over multiple jumphosts. For example::

            ["ssh://<user>:<password>@<host>", "telnet://<user>:<password>@<host>:<port>"]

        Currently there are two protocols supported: SSH and TELNET. The *port* is optional and if not specified
        the well known default protocol port is used.

        An IOS/IOS XE devices may require a privileged level password (enable password). The url parser treats
        the rest of the url (the path part + query + fragment part) as an privileged password. For example::

            ["ssh://<user>:<password>@<host>", "telnet://<user>:<password>@<host>/<enable_password>"]

        The *host* could be either the hostname or ip address.

        There could be more devices in the list representing the single or multiple jumphosts on the path
        to the target device. The condoor connects to them in a sequence starting the next connection from the
        previous host unless reaching the target device. The last url in the list is always the target device.

        The *urls* parameter can be passed as a list of the list of urls. In that case condoor treats it as
        a multiple alternative connections to the same device. During the connection or discovery phase condoor
        starts with the first connection from the list and then move sequentially to next connection list in case of
        the previous connection failure or timeout.
        This process stops when the current connection to the target devices is successful.
        The first successful connection is latched and stored in the connection class and next time when connection
        to device is being reestablished the last successful connection list is used.
        This feature is useful for providing the console connection to two processor cards of the same device.
        It could be also used if the device has two alternative Mgmt interfaces with different IP addresses.
        For example::

                [["ssh://<user>:<password>@<host>", "telnet://<user>:<password>@<ts1:2015>"],
                 ["ssh://<user>:<password>@<host>", "telnet://<user>:<password>@<ts1:2016>"]]

        In above example the *urls* parameter represents two alternative connection lists. First goes through
        terminal server on port 2015 and second goes through the same terminal server on port 2016.
        Both connections uses the same jumphost.

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
        self._discovered = False

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
        self.logger = logging.getLogger('condoor-{}'.format(id(self)))
        self._info = {}
        self._is_console = False

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
                handler = FilteredFileHandler(log_filename, pattern=re.compile("s?ftp://.*:(.*)@"))

            else:
                handler = logging.StreamHandler()
                log_dir = "./"

            handler.setFormatter(formatter)
        else:
            handler = logging.NullHandler()

        self._handler = handler

        self.logger.addHandler(self._handler)
        self.logger.setLevel(log_level)

        self._session_fd = None

        if log_dir is not None:
            try:
                self._session_fd = FilteredFile(os.path.join(log_dir, 'session.log'),
                                                mode="w", pattern=re.compile("s?ftp://.*:(.*)@"))
            except IOError:
                self._session_fd = None

        self.logger.info("Condoor version {}".format(__version__))

    def __del__(self):
        self.logger.removeHandler(self._handler)

    def _set_default_log_fd(self, logfile=None):
        if self._log_session:
            if logfile is None:
                try:
                    self._session_fd = FilteredFile(os.path.join(self._log_dir, 'session.log'), mode="a+",
                                                    pattern=re.compile("s?ftp://.*:(.*)@"))
                except (IOError, AttributeError):
                    self._session_fd = None
            else:
                self._session_fd = logfile if isinstance(logfile, file) else None

    def _get_driver_name(self):
        """
        Returns driver name based on the detected os type
        """
        driver_name = 'generic'
        if self._os_type in ["XR"]:
            driver_name = 'XR'
        elif self._os_type in ["eXR"]:
            driver_name = 'XR64'
        elif self._os_type in ["IOS", "XE"]:
            driver_name = 'IOS'
        elif self._os_type in ['NX-OS']:
            driver_name = 'NX-OS'
        elif self._os_type in ["Calvados"]:
            driver_name = "Calvados"

        return driver_name

    def _init_driver(self, driver_name='generic'):

        module_str = 'condoor.platforms.%s' % driver_name
        try:
            __import__(module_str)
            module = sys.modules[module_str]
            driver_class = getattr(module, 'Connection')
        except ImportError:
            raise GeneralError("Platform {} not supported".format(self.platform))

        driver = driver_class(
            self._hostname,
            self._nodes[self._last_driver_index],
            Controller,
            self.logger,
            self.is_console,
            account_manager=self._account_manager,
        )
        self._driver = driver

    def _shift_driver(self):
        no_hosts = len(self._nodes)
        del self._driver
        self._last_driver_index += 1
        if self._last_driver_index >= no_hosts:
            self._last_driver_index = 0

        self._init_driver()

    def _detect_console(self):
        # FIXME: Use patterns
        try:
            output = self._driver.send("show users", timeout=60)
        except CommandError:
            self.logger.debug("Command 'show users' not suported")
            return False

        for line in output.split('\n'):
            if '*' in line:
                if 'vty' in line:
                    self.logger.debug("Detected connection to vty")
                    return False
                elif 'con' in line or 'tty' in line or 'aux' in line:  # tty for NX-OS
                    self.logger.debug("Detected connection to console")
                    return True

        self.logger.debug("Connection port unknown")

    def _update_device_info(self):
        try:
            show_version = self._driver.send("show version brief", timeout=120)
        except CommandError:
            # IOS Hack - need to check if show version brief is supported on IOS/IOSXE
            show_version = self._driver.send("show version", timeout=120)

        match = re.search("Version (.*?),?(?:\[| |$)", show_version, re.MULTILINE)
        if match:
            self._os_version = match.group(1)

        match = re.search("System version: (.*)", show_version, re.MULTILINE)
        if match:
            self._os_version = match.group(1)  # override for NX-OS

        match = re.search("(XR|XE|NX-OS)", show_version)
        if match:
            self._os_type = match.group(1)
        else:
            self._os_type = 'IOS'

        if self._os_type == "XR":
            match = re.search("Build Information", show_version)
            if match:
                self._os_type = "eXR"
            match = re.search("XR Admin Software", show_version)
            if match:
                self._os_type = "Calvados"

        self._family = 'generic'
        match = re.search("^(?:  )?cisco (.*?) ", show_version, re.MULTILINE)  # NX-OS
        if match:
            self.logger.debug("Platform string: {}".format(match.group()))
            self._platform = match.group(1)
            _family = match.group(1)

        match = re.search("^[Cc]isco (.*?)(?: .*) processor", show_version, re.MULTILINE)
        if match:
            self.logger.debug("Platform string: {}".format(match.group()))
            self._platform = match.group(1)
            _family = match.group(1)

        if _family.startswith("ASR9K"):
            _family = "ASR9K"
        elif _family.startswith("NCS-6"):
            _family = "NCS6K"
        elif _family.startswith("NCS-4"):
            _family = "NCS4K"
        elif _family.startswith("NCS-50"):
            _family = "NCS5K"
        elif _family.startswith("NCS-55"):
            _family = "NCS5500"
        elif _family.startswith("CRS"):
            _family = "CRS"
        elif _family.startswith("ASR-9") and self._os_type == "XE":
            _family = "ASR900"
        elif _family.startswith("A9") and self._os_type == "IOS":
            _family = "ASR900"
        elif _family.startswith("Nexus9000") and self._os_type == "NX-OS":
            _family = "N9K"
        elif _family.startswith("NCS1") or _family.startswith("NCS-1"):
            _family = "NCS1K"

        self._family = _family

    def discovery(self, logfile=None):
        """This method detects the device details. This method discovery the several device attributes.

        Args:
            logfile (file): Optional file descriptor for session logging. The file must be open for write.
                The session is logged only if ``log_session=True`` was passed to the constructor.
                It the parameter is not passed then the default *session.log* file is created in `log_dir`.


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

        """

        self.logger.info("Device discovery process started")
        self._set_default_log_fd(logfile)

        if self._driver is None:
            self._init_driver()

        no_hosts = len(self._nodes)
        excpt = ConnectionError("Unable to connect to the device")
        for _ in xrange(no_hosts):
            try:
                self._driver.connect(logfile=self._session_fd)
                break
            except ConnectionError as e:
                self._shift_driver()
                excpt = e
        else:
            raise excpt

        self._update_device_info()

        self._prompt = self._driver.prompt
        self._is_console = self._detect_console()

        ctrl = self._driver.ctrl

        driver_name = self._get_driver_name()
        self.logger.debug("Using driver: '{}'".format(driver_name))

        if driver_name == 'generic':
            raise RuntimeError("Platform {} not supported".format(self.family))

        self._init_driver(driver_name)
        self._driver.ctrl = ctrl
        self._driver.connected = True

        self._driver.determine_hostname(self._prompt)
        self._hostname = self._driver.hostname

        # New driver initialized so need to copy detected prompts from controller
        self._driver.detected_prompts = self._driver.ctrl.detected_prompts
        # self._hostname = self._driver.hostname

        self._driver._compile_prompts()
        self._driver.collect_udi()

        self.logger.info("Hostname: '{}'".format(self.hostname))
        self.logger.info("Family: {}".format(self.family))
        self.logger.info("Platform: {}".format(self.platform))
        self.logger.info("OS: {}".format(os_names[self.os_type]))
        self.logger.info("Version: {}".format(self.os_version))
        self.logger.info("Name: {}".format(self.udi['name']))
        self.logger.info("Description: {}".format(self.udi['description']))
        self.logger.info("PID: {}".format(self.udi['pid']))
        self.logger.info("VID: {}".format(self.udi['vid']))
        self.logger.info("SN: {}".format(self.udi['sn']))
        self.logger.info("Prompt: '{}'".format(self._prompt))
        self.logger.info("Is connected to console: {}".format(self.is_console))
        self._discovered = True
        self._write_cache()
        self.logger.info("Discovery phase done")

    def _get_key(self):
        m = hashlib.md5()
        m.update(str(self._nodes))
        return m.hexdigest()

    def _write_cache(self):
        try:
            cache = shelve.open(_cache_file, 'c')
        except Exception:
            self.logger.error("Unable to open a cache file for write")
            return

        key = self._get_key()
        cache[key] = self.device_description_record
        self.logger.info("Device description record cached: {}".format(key))
        cache.close()

    def _read_cache(self):
        try:
            cache = shelve.open(_cache_file, 'r')
        except Exception:
            self.logger.warning("No cache file available. Discovery required")
            return

        key = self._get_key()
        try:
            self.device_description_record = cache[key]
            self.logger.info("Use cached device description record")
            self._discovered = True
        except KeyError:
            self.logger.debug("Device cache missed: {}".format(key))
        finally:
            cache.close()

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
        """This method connects to the device.

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

        self._read_cache()

        self._set_default_log_fd(logfile)
        if not self._discovered:
            self.discovery(logfile=logfile)

        self.logger.debug("Driver: {}".format(self._driver.platform))

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
        attempt = 1
        self.logger.info("Trying to reconnect within {} seconds".format(max_timeout))
        while expired < max_timeout:
            self.logger.debug("Reconnecting. Attempt {}".format(attempt))
            try:
                self.connect(logfile=self._session_fd)
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
                self._session_fd = None

    @property
    def platform(self):
        """Returns the string representing hardware platform model. For example: ASR-9010, ASR922, NCS-4006, etc."""
        match = re.search(r"([A-Z]{1,3}[-| ]?[0-9]{3,4})", self._driver.udi['pid'])
        if match:
            return match.group(1)
        else:
            return self._platform

    @platform.setter
    def platform(self, platform):
        self._platform = platform

    @property
    def family(self):
        """Returns the string representing hardware platform family. For example: ASR9K, ASR900, NCS6K, etc."""
        return self._family

    @property
    def prompt(self):
        """Returns the target device prompt if detected or *None*."""
        try:
            return self._prompt
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
        """Returns the string representing the target device hostname."""
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

    @property
    def is_console(self):
        """Returns *True* if the connection to the target device is over console port"""
        return self._is_console

    @property
    def name(self):
        """Returns the chassis name"""
        return self._driver.udi['name']

    @property
    def description(self):
        """Returns the chassis description."""
        return self._driver.udi['description']

    @property
    def pid(self):
        """Returns the chassis PID."""
        return self._driver.udi['pid']

    @property
    def vid(self):
        """Returns the chassis VID."""
        return self._driver.udi['vid']

    @property
    def sn(self):
        """Returns the chassis SN."""
        return self._driver.udi['sn']

    @property
    def udi(self):
        """Returns the dict representing the udi hardware record::
            {
            'description': 'ASR-9904 AC Chassis',
            'name': 'Rack 0',
            'pid': 'ASR-9904-AC',
            'sn': 'FOX1830GT5W ',
            'vid': 'V01'
            }

        """
        return self._driver.udi

    @property
    def device_info(self):
        """Returns the dict represeing the device info record::
            {
            'family': 'ASR9K',
            'os_type': 'eXR',
            'os_version': '6.1.0.06I',
            'platform': 'ASR-9904'
            }

        """
        _device_info = {
            'family': self.family,
            'platform': self.platform,
            'os_type': self.os_type,
            'os_version': self.os_version
        }
        return _device_info

    @property
    def device_description_record(self):
        return {
            'driver_name': self._get_driver_name(),
            'device_info': self.device_info,
            'udi': self.udi,
            'hostname': self.hostname,
            'console': self.is_console,
            'device_prompt': self.prompt,
            'detected_prompts': [prompt for prompt in self._driver.detected_prompts],
            'last_driver': self._last_driver_index
        }

    @device_description_record.setter
    def device_description_record(self, ddr):

        self._is_console = ddr['console']
        self._last_driver_index = ddr['last_driver']
        self._hostname = ddr['hostname']
        self._prompt = ddr['device_prompt']

        di = ddr['device_info']
        self._family = di['family']
        self._platform = di['platform']
        self._os_type = di['os_type']
        self._os_version = di['os_version']

        driver_name = ddr['driver_name']
        self._init_driver(driver_name)
        self._driver.udi = ddr['udi']
        self._driver.detected_prompts = ddr['detected_prompts']
        self._driver.determine_hostname(self._prompt)
