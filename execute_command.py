#!/usr/bin/env python
# =============================================================================
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

import logging
import getpass
import optparse
import sys

import condoor
from condoor.accountmgr import AccountManager


usage = '%prog -H url [-J url] [-d <level>] [-h] command'
usage += '\nCopyright (C) 2015 by Klaudiusz Staniek'
parser = optparse.OptionParser(usage=usage)

parser.add_option(
    '--host_url', '-H', dest='host_url', metavar='URL',
    help='''
target host url e.g.: telnet://user:pass@hostname
'''.strip())

parser.add_option(
    '--jumphost_url', '-J', dest='jumphost_url', default=None, metavar='URL',
    help='''
jump host url e.g.: ssh://user:pass@jumphostname
'''.strip())

parser.add_option(
    '--debug', '-d', dest='debug', type='str', metavar='LEVEL',
    default='CRITICAL', help='''
prints out debug information about the device connection stage.
LEVEL is a string of DEBUG, INFO, WARNING, ERROR, CRITICAL.
Default is CRITICAL.
'''.strip())

logging_map = {
    0: 60, 1: 50, 2: 40, 3: 30, 4: 20, 5: 10
}


def prompt_for_password(prompt):
    print("Password not specified in url.\n"
          "Provided password will be stored in system KeyRing\n")
    return getpass.getpass(prompt)


if __name__ == "__main__":
    options, args = parser.parse_args(sys.argv)

    args.pop(0)

    urls = []

    if options.jumphost_url:
        urls.append(options.jumphost_url)

    host_url = None
    if not options.host_url:
        parser.error('Missing host URL')

    urls.append(options.host_url)

    if len(args) > 0:
        command = " ".join(args)
    else:
        parser.error("Missing command")

    numeric_level = getattr(logging, options.debug.upper(), 50)

    try:
        import keyring
        am = AccountManager(config_file='accounts.cfg', password_cb=prompt_for_password)
    except ImportError:
        print("No keyring library installed. Password must be provided in url.")
        am = None

    try:
        conn = condoor.Connection('host', urls, account_manager=am, log_level=numeric_level)
        conn.discovery()
        conn.connect()
        try:
            output = conn.send(command)
            print output

        except condoor.CommandSyntaxError:
            print "Unknown command error"

    except condoor.ConnectionAuthenticationError as e:
        print "Authentication error: %s" % e
    except condoor.ConnectionTimeoutError as e:
        print "Connection timeout: %s" % e
    except condoor.ConnectionError as e:
        print "Connection error: %s" % e
    except condoor.GeneralError as e:
        print "Error: %s" % e