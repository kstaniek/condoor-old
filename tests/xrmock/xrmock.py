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


class TelnetServer(SocketServer.TCPServer):
    allow_reuse_address = True


class XRHandler(TelnetHandler):

    WELCOME = "\n"
    PROMPT = "RP/0/RP0/CPU0:ios#"
    TELNET_ISSUE = "\nUser Access Verification\n"  # does not work
    authNeedUser = True
    authNeedPass = True
    response_dict = {}

    @command('show', 'admin')
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

    @command('admin')
    def admin(self, params):
        filename = os.path.join(self.platform.lower(), "admin_" + "_".join(params) + ".txt")
        with open(filename) as f:
            output = f.read()
            self.writeresponse(output)

    @command('terminal')
    def terminal(self, params):
        """
        ignore
        """
        pass

    def setup(self):
        '''Called after instantiation'''
        TelnetHandler.setup(self)
        self.writeline("\nUser Access Verification\n")

    def authCallback(self, username, password):
        if username != "admin" or password != "admin": #Security comes first
            self.writeresponse("\n% Authentication failed")
            raise Exception()

    def get_response(self, command_line):
        response = self.response_dict.get(command_line, None)
        if response is None:
            filename = os.path.join(self.platform.lower(), command_line + ".txt")
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


"""
Usage example in test cases
"""
if __name__ == '__main__':
    server = TelnetServer(("127.0.0.1", 10023), NCS1KHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    raw_input("Press ENTER to stop")
    server.shutdown()
    server.server_close()

