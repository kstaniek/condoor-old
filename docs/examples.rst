Examples
========

There is a `execute_command.py <https://github.com/kstaniek/condoor/blob/master/execute_command.py>`_
example file in code repository::

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


The example help output::

    ./execute_command.py -h
    Usage: execute_command.py -H url [-J url] [-d <level>] [-h] command
    Copyright (C) 2015 by Klaudiusz Staniek

    Options:
      -h, --help            show this help message and exit
      -H URL, --host_url=URL
                            target host url e.g.: telnet://user:pass@hostname
      -J URL, --jumphost_url=URL
                            jump host url e.g.: ssh://user:pass@jumphostname
      -d LEVEL, --debug=LEVEL
                            prints out debug information about the device
                            connection stage. LEVEL is a string of DEBUG, INFO,
                            WARNING, ERROR, CRITICAL. Default is CRITICAL.


In below example Condoor connects to host 172.28.98.4 using username *cisco*. The debug level is set
to INFO and command to be executed is *show version brief*. Condoor asks for password for username *cisco* and then
stores it in local KeyRing. Subsequent command execution does not prompt a password again if password is already stored
in the KeyRing.::

    ./execute_command.py -H telnet://cisco@172.28.98.4 -d INFO show version brief

    2015-11-21 15:22:38,560     INFO: [host]: Connecting to telnet://cisco@172.28.98.4:23
    2015-11-21 15:22:42,456     INFO: [host]: [TELNET]: telnet: 172.28.98.4: Acquiring password for cisco from system KeyRing
    Password not specified in url.
    Provided password will be stored in system KeyRing

    cisco@172.28.98.4 Password:
    2015-11-21 15:22:53,110     INFO: [host]: Connected to telnet://cisco@172.28.98.4:23
    2015-11-21 15:22:53,946     INFO: [host]: Command executed successfully: 'terminal len 0'
    2015-11-21 15:22:54,781     INFO: [host]: Command executed successfully: 'terminal width 0'
    2015-11-21 15:22:58,741     INFO: [host]: Command executed successfully: 'show version'
    2015-11-21 15:22:58,742     INFO: [host]: Disconnecting from telnet://cisco@172.28.98.4:23
    2015-11-21 15:22:59,689     INFO: [host]: Disconnected
    2015-11-21 15:22:59,691     INFO: Hostname: 'ASR9K-PE2-R1'
    2015-11-21 15:22:59,691     INFO: Family: ASR9K
    2015-11-21 15:22:59,691     INFO: Platform: ASR-9010
    2015-11-21 15:22:59,691     INFO: OS: XR
    2015-11-21 15:22:59,691     INFO: Version: 5.3.1[Default]
    2015-11-21 15:22:59,691     INFO: Prompt: 'RP/0/RSP0/CPU0:ASR9K-PE2-R1#'
    2015-11-21 15:22:59,691     INFO: [ASR9K-PE2-R1]: Connecting to telnet://cisco@172.28.98.4:23
    2015-11-21 15:23:11,075     INFO: [ASR9K-PE2-R1]: Connected to telnet://cisco@172.28.98.4:23
    2015-11-21 15:23:11,911     INFO: [ASR9K-PE2-R1]: Command executed successfully: 'terminal exec prompt no-timestamp'
    2015-11-21 15:23:12,747     INFO: [ASR9K-PE2-R1]: Command executed successfully: 'terminal len 0'
    2015-11-21 15:23:13,582     INFO: [ASR9K-PE2-R1]: Command executed successfully: 'terminal width 0'
    2015-11-21 15:23:14,441     INFO: [ASR9K-PE2-R1]: Command executed successfully: 'show version brief'


    Cisco IOS XR Software, Version 5.3.1[Default]
    Copyright (c) 2015 by Cisco Systems, Inc.

    ROM: System Bootstrap, Version 0.73(c) 1994-2012 by Cisco Systems,  Inc.

    ASR9K-PE2-R1 uptime is 2 days, 16 hours, 46 minutes
    System image file is "disk0:asr9k-os-mbi-5.3.1/0x100305/mbiasr9k-rsp3.vm"

    cisco ASR9K Series (Intel 686 F6M14S4) processor with 12582912K bytes of memory.
    Intel 686 F6M14S4 processor at 2134MHz, Revision 2.174
    ASR 9010 8 Line Card Slot Chassis with V1 AC PEM

    2 Management Ethernet
    8 TenGigE
    8 DWDM controller(s)
    8 WANPHY controller(s)
    1 SONET/SDH
    503k bytes of non-volatile configuration memory.
    6271M bytes of hard disk.
    11817968k bytes of disk0: (Sector size 512 bytes).
    11817968k bytes of disk1: (Sector size 512 bytes).

