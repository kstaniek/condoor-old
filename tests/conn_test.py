# =============================================================================
# url_test
#
# Copyright (c)  2014, Cisco Systems
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

import condoor
import sys
import pytest

import logging

logging.basicConfig(
        format='%(asctime)-15s %(levelname)8s: %(message)s',
        level=logging.DEBUG)


from condoor.exceptions import ConnectionError, ConnectionAuthenticationError

def connection(urls):

    conn = condoor.make_connection_from_urls("test", urls)
    conn.connect(sys.stderr)
    #conn.connect()
    output = conn.send('sh install inactive summary')
    print output
    output = conn.send('sh install active summary')
    print output
    #output = conn.send('sh install committed summary')
    #print output
    #output = conn.send('sh inventory')
    #print output

    conn.disconnect()

def mkurl(protocol, user, password, node):
    return "{}://{}:{}@{}".format(protocol, user, password, node)




@pytest.mark.parametrize("urls", [
    (pytest.mark.xfail(['telnet://<user>:<password>@1.1.1.1', 'telnet://<user>:<password>@mercy'], raises=ConnectionError)),
    (pytest.mark.xfail(['telnet://<user>:<password>@sj20lab-as1', 'telnet://<user>:<password@1.1.1.1'], raises=ConnectionError)),
    (pytest.mark.xfail(['telnet://<user>:wrong_pass@sj20lab-as1', 'telnet://<user>:<password>@mercy'], raises=ConnectionError)),
    (pytest.mark.xfail(['telnet://<user>:<password>@sj20lab-as1', 'telnet://<user>:wrong_pass@mercy'], raises=ConnectionError)),
    (pytest.mark.xfail(['ssh://wrong_user:<password>@sj20lab-as1', 'telnet://<user>:<password>@mercy'], raises=ConnectionAuthenticationError)),
    (pytest.mark.xfail(['ssh://<user>:<password>@1.1.1.1', 'telnet://cisco:C1sco123@bdlk1-b05-ts-01:2032'], raises=ConnectionError)),
    (pytest.mark.xfail(['ssh://<user>:<password>@localhost', 'ssh://<user>:<password>@1.1.1.1', 'telnet://cisco:C1sco123@bdlk1-b05-ts-01:2032'], raises=ConnectionError)),
    (pytest.mark.xfail(['telnet://<user>:<password>@people', 'telnet://<user>:<password>@1.1.1.1', 'telnet://<user>:<password>@mercy'], raises=ConnectionError)),
    (pytest.mark.xfail(['ssh://<user>:<password>@people', 'ssh://<user>:<password>@people', 'telnet://<user>:<passowrd>@1.1.1.1', 'telnet://<user>:<password>@mercy'], raises=ConnectionError)),
    (pytest.mark.xfail(['telnet://lab:lab@10.105.226.125', 'telnet://lab:lab@10.105.226.126'], raises=ConnectionError)),
    (['ssh://<user>:<password>@sj20lab-as1', 'telnet://<user>:<password>@mercy']),
    (['telnet://<user>:<password>@people', 'telnet://<user>:<password>@mercy']),
    (['telnet://<user>:<password>@mercy']),
    (['ssh://<user>:<password>@localhost', 'telnet://cisco:C1sco123@bdlk1-b05-ts-01:2032']),
    (['ssh://<user>:<password>@sweet-brew', 'telnet://cisco:C1sco123@bdlk1-b05-ts-01:2032']),
    (['telnet://cisco:C1sco123@bdlk1-b05-ts-01:2032']),
    (['ssh://<user>:<password>@localhost', 'ssh://<user>:<password>@localhost', 'telnet://cisco:C1sco123@bdlk1-b05-ts-01:2032']),
    (['ssh://<user>:<password>@people', 'telnet://cisco:C1sco123@bdlk1-b05-ts-01:2032']),
    # # -- no longer works  (['telnet://lab:lab@10.105.226.125:20421']),
    (['ssh://lab:lab@gsr-india03-lnx', 'telnet://lab:lab@5.34.16.101']),
    (['telnet://lab:lab@10.105.226.125', 'telnet://lab:lab@5.34.16.101']),
    (['telnet://lab:lab@10.105.226.125:2065']),
    (['ssh://<user>:<password>@sweet-brew-1', 'telnet://lab:lab@10.105.226.125:2065']),
    (['telnet://:ww@10.50.2.225', 'telnet://ww:ww@192.168.0.4']),
    (['telnet://10.50.2.225', 'telnet://ww:ww@192.168.0.4']),
])







def test_eval(username, password, urls):
    new_urls = []
    for url in urls:
        if username is not None:
            url = url.replace("<user>", str(username))
        if password is not None:
            url = url.replace("<password>", str(password))
        new_urls.append(url)
    print new_urls
    connection(new_urls)

# class TestClass:
#     def test_1(self, username, password):
#         url1 = mkurl('telnet', username, password, "1.1.1.1")
#         url2 = mkurl('telnet', username, password, "mercy")
#         with pytest.raises(condoor.exceptions.ConnectionError) as excinfo:
#             urls = [ url1, url2 ]
#             connection(urls)
#
#
#
#     def test_2(self):
#         url1 = mkurl('telnet', "", "ww", "10.50.2.225")
#         url2 = mkurl('telnet', "ww", "ww", "192.168.0.4")
#         connection([url1, url2])
#
#         return ["info1: did you know that ...", "did you?"]
