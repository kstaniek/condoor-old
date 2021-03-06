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

import socket
import time


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

    for family, socktype, proto, cannonname, sockaddr in addresses:
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
