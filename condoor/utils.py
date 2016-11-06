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

import logging
import socket
import time
import re


def delegate(attribute_name, method_names):
    """Passes the call to the attribute called attribute_name for
    every method listed in method_names.
    """
    # hack for python 2.7 as nonlocal is not available
    d = {
        'attribute': attribute_name,
        'methods': method_names
    }

    def decorator(cls):
        attribute = d['attribute']
        if attribute.startswith("__"):
            attribute = "_" + cls.__name__ + attribute
        for name in d['methods']:
            setattr(cls, name, eval("lambda self, *a, **kw: "
                                    "self.{0}.{1}(*a, **kw)".format(attribute, name)))
        return cls
    return decorator


def to_list(item):
    """
    If the given item is iterable, this function returns the given item.
    If the item is not iterable, this function returns a list with only the
    item in it.

    @type  item: object
    @param item: Any object.
    @rtype:  list
    @return: A list with the item in it.
    """
    if hasattr(item, '__iter__'):
        return item
    return [item]


def is_reachable(host, port=23):
    """
    This function check reachability for specified hostname/port
    It tries to open TCP socket.
    It supports IPv6.
    :param host: hostname or ip address string
    :rtype: str
    :param port: tcp port number
    :rtype: number
    :return: True if host is reachable else false
    """

    try:
        addresses = socket.getaddrinfo(
            host, port, socket.AF_UNSPEC, socket.SOCK_STREAM
        )
    except socket.gaierror:
        return False

    for family, _, _, _, sockaddr in addresses:
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            sock.connect(sockaddr)
        except IOError:
            continue

        sock.shutdown(socket.SHUT_RDWR)
        sock.close()
        # Wait 2 sec for socket to shutdown
        time.sleep(2)
        break
    else:
        return False
    return True


def pattern_to_str(pattern):
    """
    This function convert pattern to string. If pattern is string it returns itself,
    if pattern is SRE_Pattern then return pattern attribute
    :param pattern: pattern object or string
    :return: str: pattern sttring
    """
    if isinstance(pattern, str):
        return pattern
    else:
        return pattern.pattern


def levenshtein_distance(a, b):
    """
    This calculates the Levenshtein distance between string a and b.

    :param a: String - input string a
    :param b: String - input string b
    :return: Number - Levenshtein Distance between string a and b
    """

    n, m = len(a), len(b)
    if n > m:
        a, b = b, a
        n, m = m, n
    current = range(n + 1)
    for i in range(1, m + 1):
        previous, current = current, [i] + [0] * n
        for j in range(1, n + 1):
            add, delete = previous[j] + 1, current[j - 1] + 1
            change = previous[j - 1]
            if a[j - 1] != b[i - 1]:
                change += + 1
            current[j] = min(add, delete, change)
    return current[n]


def parse_inventory(inventory_output=None):
    udi = {
        "name": "",
        "description": "",
        "pid": "",
        "vid": "",
        "sn": ""
    }
    if inventory_output is None:
        return udi

    # find the record with chassis text in name or descr
    capture_next = False
    chassis_udi_text = None
    for line in inventory_output.split('\n'):
        lc_line = line.lower()
        if 'chassis' in lc_line and 'name' in lc_line and 'descr':
            capture_next = True
            chassis_udi_text = line
            continue
        if capture_next:
            inventory_output = chassis_udi_text + "\n" + line
            break

    match = re.search(r"(?i)NAME: (?P<name>.*?),? (?i)DESCR", inventory_output, re.MULTILINE)
    if match:
        udi['name'] = match.group('name').strip('" ,')

    match = re.search(r"(?i)DESCR: (?P<description>.*)", inventory_output, re.MULTILINE)
    if match:
        udi['description'] = match.group('description').strip('" ')

    match = re.search(r"(?i)PID: (?P<pid>.*?),? ", inventory_output, re.MULTILINE)
    if match:
        udi['pid'] = match.group('pid')

    match = re.search(r"(?i)VID: (?P<vid>.*?),? ", inventory_output, re.MULTILINE)
    if match:
        udi['vid'] = match.group('vid')

    match = re.search(r"(?i)SN: (?P<sn>.*)", inventory_output, re.MULTILINE)
    if match:
        udi['sn'] = match.group('sn')
    return udi


class FilteredFile(object):
    __slots__ = ['_file', '_pattern']

    def __init__(self, filename, mode="r", pattern=None):
        object.__setattr__(self, '_pattern', pattern)
        object.__setattr__(self, '_file', open(filename, mode))

    def __getattr__(self, name):
        return getattr(self._file, name)

    def __setattr__(self, name, value):
        setattr(self._file, name, value)

    def write(self, text):
        if self._pattern:
            # pattern already compiled no need to check
            result = re.search(self._pattern, text)
            if result:
                for g in result.groups():
                    if g:
                        text = text.replace(g, "***")
        self._file.write(text)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._file.close()

    def __enter__(self):
        return self


class FilteredFileHandler(logging.FileHandler):
    def __init__(self, filename, mode='a', encoding=None, delay=0, pattern=None):
        self.pattern = pattern
        logging.FileHandler.__init__(self, filename, mode=mode, encoding=encoding, delay=delay)

    def _open(self):
        return FilteredFile(self.baseFilename, self.mode, self.pattern)
