# =============================================================================
# exceptions
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


class GeneralError(Exception):
    """General error"""
    def __init__(self, message=None, host=None):
        """The class constructor.

        Args:
            message (str): Custom message to be passed to the exceptions. Defaults to *None*.
                If *None* then the general class *__doc__* is used.
            host (str): Custom string which can be used to enhance the exception message by adding the "`host`: "
                prefix to the message string. Defaults to *None*. If `host` is *None* then message stays unchanged.
        """
        self.message = message
        self.hostname = str(host)

    def __str__(self):
        message = self.message or self.__class__.__doc__
        return "{}: {}".format(self.hostname, message) if self.hostname else message


class InvalidHopInfoError(GeneralError):
    """Invalid device connection parameters"""
    pass


class ConnectionError(GeneralError):
    """General connection error"""
    pass


class ConnectionAuthenticationError(ConnectionError):
    """Connection authentication error"""
    pass


class ConnectionTimeoutError(ConnectionError):
    """Connection timeout error"""
    pass


class CommandError(GeneralError):
    """Command execution error"""
    def __init__(self, message=None, host=None, command=None):
        """The class constructor.

        Args:
            message (str): Custom message to be passed to the exceptions. Defaults to *None*.
                If *None* then the general class *__doc__* is used.
            host (str): Custom string which can be used to enhance the exception message by adding the "`host`: "
                prefix to the message string. Defaults to *None*. If `host` is *None* then message stays unchanged.
            command (str): Custom string which can be used enhance the exception message by adding the
                "`command`" suffix to the message string. Defaults to *None*. If `command` is *None* then the message
                stays unchanged.
        """
        GeneralError.__init__(self, message, host)
        self.command = command

    def __str__(self):
        message = self.message or self.__class__.__doc__
        message = "{}: '{}'".format(message, self.command) \
            if self.command else message
        message = "{}: {}".format(self.hostname, message) \
            if self.hostname else message
        return message


class CommandSyntaxError(CommandError):
    """Command syntax error"""
    pass


class CommandTimeoutError(CommandError):
    """Command timeout error"""
    pass
