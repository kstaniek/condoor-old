#!/usr/bin/env python
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
import threading
import sys


class TelnetServer(SocketServer.TCPServer):
    allow_reuse_address = True


class XRHandler(TelnetHandler):

    WELCOME = "\n"
    PROMPT = "RP/0/RP0/CPU0:ios#"
    TELNET_ISSUE = "\nUser Access Verification\n"  # does not work
    AUTH_MESSAGE = "\nUser Access Verification\n"
    authNeedUser = True
    authNeedPass = True
    response_dict = {}
    action_dict = {}
    username = "admin"
    password = "admin"
    PROMPT_USER = "Username: "
    PROMPT_PASS = "Password: "

    @command(['show', 'admin'])
    def cmd(self, params):
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
        ignore
        """
        pass

    def authCallback(self, username, password):
        if username != self.username or password != self.password:
            raise Exception()

    def get_response(self, command_line):
        response = self.response_dict.get(command_line, None)
        if response is None:
            directory = os.path.dirname(os.path.realpath(__file__))
            filename = os.path.join(directory, self.platform.lower(), command_line + ".txt")
            try:
                with open(filename) as f:
                    response = f.read()
            except:
                response = None
        return response

    def get_action(self, command_line, when):
        action_name = None
        data = self.action_dict.get(command_line, None)
        if data:
            action_name = data.get(when, None)
        return action_name

    def authentication_ok(self):
        for _ in range(3):
            self.writeline("\nUser Access Verification\n")
            result = TelnetHandler.authentication_ok(self)
            if result:
                break
        else:
            self.writeresponse("\n% Authentication failed")

        return result

    def authentication_ok(self):
        '''Checks the authentication and sets the username of the currently connected terminal.  Returns True or False'''
        username = None
        password = None
        for _ in range(3):
            self.writeline("\nUser Access Verification\n")
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
                        self.write("\n")
                try:
                    self.authCallback(username, password)
                except:
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
        else:
            self.writeresponse("\n% Authentication failed")
            return False


class NCS1KHandler(XRHandler):
    platform = "NCS1K"
    response_dict = {
        'show_install_request': "10.77.132.127: Permission denied"
    }
    action_dict = {
        'show_install_request': {'AFTER': 'disconnect'}
    }

    def disconnect(self):
        self.RUNSHELL = False


# """
# Usage example in test cases
# """
# if __name__ == '__main__':
#     server = TelnetServer(("127.0.0.1", 10023), NCS1KHandler)
#     server_thread = threading.Thread(target=server.serve_forever)
#     server_thread.daemon = True
#     server_thread.start()
#     raw_input("Press ENTER to stop")
#     server.shutdown()
#     server.server_close()
#
