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


from condoor.hopinfo import make_hop_info_from_url


class TestClass:
    def test_url_telnet(self):
        url = "telnet://user:pass@1.1.1.1"
        hop_info = make_hop_info_from_url(url)
        assert hop_info.protocol == 'telnet'
        assert hop_info.username == 'user'
        assert hop_info.password == 'pass'
        assert hop_info.hostname == '1.1.1.1'
        assert hop_info.port == 23

    def test_url_telnet_2048(self):
        url = "telnet://user:pass@1.1.1.1:2048"
        hop_info = make_hop_info_from_url(url)
        assert hop_info.protocol == 'telnet'
        assert hop_info.username == 'user'
        assert hop_info.password == 'pass'
        assert hop_info.hostname == '1.1.1.1'
        assert hop_info.port == 2048

    def test_url_telnet_empty_user(self):
        url = "telnet://:pass@1.1.1.1:2048"
        hop_info = make_hop_info_from_url(url)
        assert hop_info.protocol == 'telnet'
        assert hop_info.username == ''
        assert hop_info.password == 'pass'
        assert hop_info.hostname == '1.1.1.1'
        assert hop_info.port == 2048

    def test_url_telnet_empty_password(self):
        url = "telnet://user:@1.1.1.1:2048"
        hop_info = make_hop_info_from_url(url)
        assert hop_info.protocol == 'telnet'
        assert hop_info.username == 'user'
        assert hop_info.password == ''
        assert hop_info.hostname == '1.1.1.1'
        assert hop_info.port == 2048

    def test_url_telnet_no_password(self):
        url = "telnet://user@1.1.1.1:2048"
        hop_info = make_hop_info_from_url(url)
        assert hop_info.protocol == 'telnet'
        assert hop_info.username == 'user'
        assert hop_info.password is None
        assert hop_info.hostname == '1.1.1.1'
        assert hop_info.port == 2048

    def test_url_telnet_empty_user_password(self):
        url = "telnet://:@1.1.1.1:2048"
        hop_info = make_hop_info_from_url(url)
        assert hop_info.protocol == 'telnet'
        assert hop_info.username == ''
        assert hop_info.password == ''
        assert hop_info.hostname == '1.1.1.1'
        assert hop_info.port == 2048

    def test_url_telnet_no_user_password(self):
        url = "telnet://1.1.1.1:2048"
        hop_info = make_hop_info_from_url(url)
        assert hop_info.protocol == 'telnet'
        assert hop_info.username is None
        assert hop_info.password is None
        assert hop_info.hostname == '1.1.1.1'
        assert hop_info.port == 2048

    def test_url_ssh(self):
        url = "ssh://user:pass@1.1.1.1"
        hop_info = make_hop_info_from_url(url)
        assert hop_info.protocol == 'ssh'
        assert hop_info.username == 'user'
        assert hop_info.password == 'pass'
        assert hop_info.hostname == '1.1.1.1'
        assert hop_info.port == 22

    def test_url_ssh_2048(self):
        url = "ssh://user:pass@1.1.1.1:2048"
        hop_info = make_hop_info_from_url(url)
        assert hop_info.protocol == 'ssh'
        assert hop_info.username == 'user'
        assert hop_info.password == 'pass'
        assert hop_info.hostname == '1.1.1.1'
        assert hop_info.port == 2048

    def test_url_ssh_empty_user(self):
        url = "ssh://:pass@1.1.1.1:2048"
        hop_info = make_hop_info_from_url(url)
        assert hop_info.protocol == 'ssh'
        assert hop_info.username == ''
        assert hop_info.password == 'pass'
        assert hop_info.hostname == '1.1.1.1'
        assert hop_info.port == 2048

    def test_url_ssh_empty_password(self):
        url = "ssh://user:@1.1.1.1:2048"
        hop_info = make_hop_info_from_url(url)
        assert hop_info.protocol == 'ssh'
        assert hop_info.username == 'user'
        assert hop_info.password == ''
        assert hop_info.hostname == '1.1.1.1'
        assert hop_info.port == 2048

    def test_url_ssh_no_password(self):
        url = "ssh://user@1.1.1.1:2048"
        hop_info = make_hop_info_from_url(url)
        assert hop_info.protocol == 'ssh'
        assert hop_info.username == 'user'
        assert hop_info.password is None
        assert hop_info.hostname == '1.1.1.1'
        assert hop_info.port == 2048

    def test_url_ssh_empty_user_password(self):
        url = "ssh://:@1.1.1.1:2048"
        hop_info = make_hop_info_from_url(url)
        assert hop_info.protocol == 'ssh'
        assert hop_info.username == ''
        assert hop_info.password == ''
        assert hop_info.hostname == '1.1.1.1'
        assert hop_info.port == 2048

    def test_url_ssh_no_user_password(self):
        url = "ssh://1.1.1.1:2048"
        hop_info = make_hop_info_from_url(url)
        assert hop_info.protocol == 'ssh'
        assert hop_info.username is None
        assert hop_info.password is None
        assert hop_info.hostname == '1.1.1.1'
        assert hop_info.port == 2048

    def test_url_ssh_no_user_nor_enable_password(self):
        url = "ssh://1.1.1.1:2048"
        hop_info = make_hop_info_from_url(url)
        assert hop_info.protocol == 'ssh'
        assert hop_info.username is None
        assert hop_info.password is None
        assert hop_info.hostname == '1.1.1.1'
        assert hop_info.port == 2048
        assert hop_info.enable_password is None

    def test_url_telnet_no_user_password_and_enable(self):
        url = "telnet://1.1.1.1:2048/!@#$%^&*()1/2345678asdfgh"
        hop_info = make_hop_info_from_url(url)
        assert hop_info.protocol == 'telnet'
        assert hop_info.username is None
        assert hop_info.password is None
        assert hop_info.hostname == '1.1.1.1'
        assert hop_info.port == 2048
        assert hop_info.enable_password == "!@#$%^&*()1/2345678asdfgh"

    def test_url_telnet_no_user_password_and_enable_no_port(self):
        url = "telnet://1.1.1.1/!@#$%^&*()1/2345678asdfgh"
        hop_info = make_hop_info_from_url(url)
        assert hop_info.protocol == 'telnet'
        assert hop_info.username is None
        assert hop_info.password is None
        assert hop_info.hostname == '1.1.1.1'
        assert hop_info.port == 23
        assert hop_info.enable_password == "!@#$%^&*()1/2345678asdfgh"

    def test_url_telnet_two_ip(self):
        url = "telnet://1.1.1.1,2.2.2.2:23,34/!@#$%^&*()1/2345678asdfgh"
        hop_info = make_hop_info_from_url(url)
        assert hop_info.protocol == 'telnet'
        assert hop_info.username is None
        assert hop_info.password is None
        assert hop_info.hostname == '1.1.1.1,2.2.2.2'
        assert hop_info.port == 23, 24
        assert hop_info.enable_password == "!@#$%^&*()1/2345678asdfgh"
