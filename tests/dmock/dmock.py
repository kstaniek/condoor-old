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


from telnetsrv.threaded import TelnetHandler, command
import SocketServer
import os


class TelnetServer(SocketServer.TCPServer):
    allow_reuse_address = True


class DeviceHandler(TelnetHandler):
    """Generic device handler"""

    # Dictionary to alter the command output provided in the text file. Usefull for test cases where similating
    # specific device responses is needed, i.e.:
    # response_dict = {
    #    'show_install_request': "10.77.132.127: Permission denied"
    # }
    response_dict = {}

    # Dictionary containing the method names from the Handler to be executed before and after specific command, i.e.:
    # action_dict = {
    #     'show_install_request': {'AFTER': 'disconnect'}
    # }
    action_dict = {}

    authNeedUser = True
    authNeedPass = True
    USERNAME = "admin"
    PASSWORD = "admin"
    AUTH_MESSAGE = "User Access Verification\n"
    PROMPT_USER = "Username: "
    PROMPT_PASS = "Password: "
    PROMPT = "IOS#"
    WELCOME = "\n"
    #GOODBYE = "Connection closed by foreign host."
    GOODBYE = None

    def authCallback(self, username, password):
        if self.authNeedUser:
            if username != self.USERNAME:
                raise Exception()
        if self.authNeedPass:
            if password != self.PASSWORD:
                raise Exception()
        return True

        # if username != self.USERNAME or password != self.PASSWORD:
        #     raise Exception()
        # return True


    def get_response(self, command_line):
        response = self.response_dict.get(command_line, None)
        if response is None:
            directory = os.path.dirname(os.path.realpath(__file__))
            filename = os.path.join(directory, self.platform.lower(), command_line + ".txt")
            try:
                with open(filename) as f:
                    response = f.read()
            except IOError:
                response = None
        return response

    def get_action(self, command_line, when):
        action_name = None
        data = self.action_dict.get(command_line, None)
        if data:
            action_name = data.get(when, None)
        return action_name

    def cmd(self, params):
        """Default command handler"""
        params.insert(0, self.input.cmd)
        command_line = "_".join(params)
        response = self.get_response(command_line)
        action_name = self.get_action(command_line, 'BEFORE')
        if action_name:
            action = getattr(self, action_name, None)
            if action:
                action()

        if response:
            self.writeresponse(response)

        action_name = self.get_action(command_line, 'AFTER')
        if action_name:
            action = getattr(self, action_name, None)
            if action:
                action()

    @command('terminal')
    def terminal(self, params):
        """
        Just accept the terminal command. No action.
        """
        pass

    @command('wrongcommand')
    def wrongcommand(self, params):
        self.writeresponse(self.WRONGCOMMAND)

    @command('exit')
    def exit(self, params):
        self.RUNSHELL = False
        if self.GOODBYE:
            self.writeline(self.GOODBYE)

    def authentication_ok(self):
        """Checks the authentication and sets the username of the currently connected terminal.
        Returns True or False
        """
        username = None
        password = None
        for _ in range(3):
            self.writeline(self.AUTH_MESSAGE)
            if self.authCallback:
                if self.authNeedUser:
                    username = self.readline(prompt=self.PROMPT_USER, use_history=False)
                    if username == 'QUIT':
                        self.RUNSHELL = False
                        return True

                if self.authNeedPass:
                    password = self.readline(echo=False, prompt=self.PROMPT_PASS, use_history=False)
                    if password == 'QUIT':
                        self.RUNSHELL = False
                        return True

                    if self.DOECHO:
                        pass
                        #self.write("\n")
                try:
                    self.authCallback(username, password)
                except Exception:
                    self.username = None
                    continue

                else:
                    # Successful authentication
                    self.username = username
                    return True
            else:
                # No authentication desired
                self.username = None
                return True

        self.writeresponse(self.AUTH_FAILED_MESSAGE)
        return False


class XRHandler(DeviceHandler):
    """Generic IOSXR handler"""

    PROMPT = "RP/0/RP0/CPU0:ios#"
    TELNET_ISSUE = "\nUser Access Verification\n"  # does not work
    AUTH_MESSAGE = "\nUser Access Verification\n"
    AUTH_FAILED_MESSAGE = "\n% Authentication failed"
    PROMPT_USER = "Username: "
    PROMPT_PASS = "Password: "
    WRONGCOMMAND = """                    ^
% Invalid input detected at '^' marker."""

    response_dict = {"wrongcommand": WRONGCOMMAND}

    @command(['show', 'admin'])
    def show_admin(self, params):
        self.cmd(params=params)


class ASR9KHandler(XRHandler):
    """
    Standard ASR9000 Handler
    """
    platform = "ASR9K"


class ASR9K64Handler(XRHandler):
    """
    Standard ASR9000 64 bit Handler
    """
    platform = "ASR9K-64"


class NCS1KHandler(XRHandler):
    platform = "NCS1K"
    response_dict = {
        "show_install_request": "10.77.132.127: Permission denied"}

    action_dict = {
        "show_install_request": {"AFTER": "disconnect"}
    }

    def disconnect(self):
        self.RUNSHELL = False


class NCS5500Handler(XRHandler):
    platform = "NCS5500"


class NXOSHandler(DeviceHandler):

    WELCOME = """Cisco Nexus Operating System (NX-OS) Software
TAC support: http://www.cisco.com/tac
Copyright (C) 2002-2016, Cisco and/or its affiliates.
All rights reserved.
The copyrights to certain works contained in this software are
owned by other third parties and used and distributed under their own
licenses, such as open source.  This software is provided "as is," and unless
otherwise stated, there is no warranty, express or implied, including but not
limited to warranties of merchantability and fitness for a particular purpose.
Certain components of this software are licensed under
the GNU General Public License (GPL) version 2.0 or
GNU General Public License (GPL) version 3.0  or the GNU
Lesser General Public License (LGPL) Version 2.1 or
Lesser General Public License (LGPL) Version 2.0.
A copy of each such license is available at
http://www.opensource.org/licenses/gpl-2.0.php and
http://opensource.org/licenses/gpl-3.0.html and
http://www.opensource.org/licenses/lgpl-2.1.php and
http://www.gnu.org/licenses/old-licenses/library.txt."""
    PROMPT = "switch#"
    TELNET_ISSUE = "\nUser Access Verification"  # does not work
    AUTH_MESSAGE = "\nUser Access Verification"
    AUTH_FAILED_MESSAGE = "\n% Authentication failed"
    PROMPT_USER = "switch login: "
    PROMPT_PASS = "Password: "
    WRONGCOMMAND = """         ^
% Invalid command at '^' marker."""

    @command('show')
    def show(self, params):
        self.cmd(params=params)


class NX9KHandler(NXOSHandler):
    platform = "N9K"


class SunHandler(DeviceHandler):
    PROMPT = "TEST "  # Intentionally wierd prompt
    WELCOME = "Last login: Wed Jul 27 00:44:30 from localhost"

    authNeedUser = True
    authNeedPass = True
    response_dict = {}
    action_dict = {}
    USERNAME = "admin"
    PASSWORD = "admin"
    PROMPT_USER = "login:"
    PROMPT_PASS = "This is your AD password:"

    def authCallback(self, username, password):
        if password != self.PASSWORD:
            raise Exception()
        return True

    def authentication_ok(self):
        username = None
        password = None
        for _ in range(1):
            if self.authCallback:

                if self.authNeedPass:
                    password = self.readline(echo=False, prompt=self.PROMPT_PASS, use_history=False)
                    if password == 'QUIT':
                        self.RUNSHELL = False
                        return True

                    if self.DOECHO:
                        self.write("\n")
                try:
                    self.authCallback(None, password)
                except Exception:
                    self.username = None
                    continue

                else:
                    # Successful authentication
                    self.username = username
                    return True
            else:
                # No authentication desired
                self.username = None
                return True
        self.writeresponse("Login incorrect")
        return False

    @command('telnet')
    def telnet(self, params):
        self.writeresponse("""Trying host1...
Connected to host1.
Escape character is '^]'.""")


class IOSXEHandler(DeviceHandler):
    AUTH_MESSAGE = "\n\nUser Access Verification\n"
    PROMPT_PASS = "Password: Kerberos: No default realm defined for Kerberos!\n"
    PROMPT_PASS_E = "Password: "
    AUTH_FAILED_MESSAGE = "% Bad passwords\n"
    ENABLE_FAILED_MESSAGE = "% Bad secrets\n"
    PROMPT = "IOS#"
    WELCOME = ""
    ENABLE_PASSWORD = "admin"
    WRONGCOMMAND = "% Bad IP address or host name% Unknown command or computer name, or unable to find computer address"

    @command(['show'])
    def show(self, params):
        self.cmd(params=params)

    @command(['enable', 'en'])
    def enable(self, params):
        for _ in range(3):
            password = self.readline(echo=False, prompt=self.PROMPT_PASS_E, use_history=False)
            if password == 'QUIT':
                self.RUNSHELL = False
                return True
            if self.DOECHO:
                self.write("\n")
            if password == self.ENABLE_PASSWORD:
                self.PROMPT = self.PROMPT[:-1] + "#"
                break
        else:
            self.writeresponse(self.ENABLE_FAILED_MESSAGE)

    @command(['disable'])
    def disable(self, params):
        self.PROMPT = self.PROMPT[:-1] + ">"


class ASR920Handler(IOSXEHandler):
    platform = "ASR920"
    authNeedUser = False
    PROMPT = "CSG-5502-ASR920>"


class ASR903Handler(IOSXEHandler):
    platform = "ASR903"
    authNeedUser = False
    PROMPT = "PAN-5205-ASR903>"

class ASR901Handler(IOSXEHandler):
    platform = "ASR901"
    authNeedUser = False
    PROMPT = "CSG-1202-ASR901>"


if __name__ == '__main__':

    from threading import Thread
    server = TelnetServer(("127.0.0.1", 10025), ASR920Handler)
    server_thread = Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    raw_input("Press Enter to continue...")

    server.shutdown()
    server.server_close()
    server_thread.join()

