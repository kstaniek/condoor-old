# =============================================================================
# protocols
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


from collections import defaultdict

from base import Protocol
from ssh import SSH
from telnet import Telnet
from telnet import TelnetConsole
from functools import partial

protocol2object = defaultdict(
    Protocol, {
        'ssh': SSH,
        'telnet': Telnet,
        'telnet_console': TelnetConsole,
    }
)


def make_protocol(controller, node_info, prompt):
    spawn = False if controller.connected else True
    logfile = controller.session_log
    account_manager = controller.account_mgr
    platform = 'jumphost' if not controller.is_target else controller.platform.platform
    pattern_manager = controller.platform.pattern_manager
    get_pattern = partial(pattern_manager.get_pattern, platform)

    protocol_name = node_info.protocol
    if controller.platform.is_console:
        protocol_name += '_console'

    return protocol2object[protocol_name](
        controller,
        node_info,
        spawn,
        prompt,
        get_pattern,
        account_manager,
        logfile)
