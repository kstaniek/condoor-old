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

from unittest import TestCase

from condoor.controllers.fsm import FSM, action
import condoor
import pexpect
from mock import Mock
from functools import partial


class TestFSM(TestCase):
    def setUp(self):
        pass

    def test_fsm_max_transitions(self):
        """FSM: Test the maximum transitions sentil"""

        class Ctrl(object):
            logger = None
            hostname = "hostname"

            def expect(self, events, searchwindowsize, timeout):
                pass

        ctrl = Mock(spec=Ctrl)
        ctrl.expect.return_value = 0
        ctrl.counter = 0

        @action
        def action1(ctx):
            self.assertEqual(ctx.event, 0)
            self.assertEqual(ctx.finished, False)
            self.assertEqual(ctx.fsm_name, "MAX-TR")
            self.assertEqual(ctx.msg, "")
            self.assertEqual(ctx.pattern, pexpect.TIMEOUT)
            self.assertEqual(ctx.state, 0)
            ctx.ctrl.counter += 1
            return True

        events = [pexpect.TIMEOUT]

        transitions = [
            (pexpect.TIMEOUT, [0], 0, action1, 1)
        ]

        sm = FSM("MAX-TR", ctrl, events=events, transitions=transitions, init_pattern=None,
                 timeout=1, max_transitions=5)
        result = sm.run()

        self.assertEqual(ctrl.counter, 5)
        self.assertFalse(result)

    def test_fsm_action(self):
        """FSM: Test different actions"""

        class Ctrl(object):
            logger = None
            hostname = "hostname"

            def expect(self, events, searchwindowsize, timeout):
                pass

        ctrl = Mock(spec=Ctrl)
        ctrl.expect.return_value = 0
        ctrl.counter = 0
        ctrl.logger.setLevel(10)

        @action
        def action1(ctx):
            ctx.ctrl.expect.return_value = 1
            self.assertEqual(str(ctx), "FSM Context:E=0,S=0,FI=False,M=''")
            return True

        @action
        def action2(ctx):
            ctx.ctrl.expect.return_value = 2
            self.assertEqual(str(ctx), "FSM Context:E=1,S=1,FI=False,M=''")
            return True

        events = ["STATE1", "STATE2", "STATE3"]

        transitions = [
            ("STATE1", [0], 1, action1, 1),
            ("STATE2", [1], 2, action2, 1),
            ("STATE3", [2], 3, None, 1),
            ("STATE3", [3], -1, condoor.ConnectionTimeoutError("Error"), 0),
            ("UNKNOWN", [4], -1, None, 0)
        ]

        sm = FSM("FSM", ctrl, events=events, transitions=transitions, init_pattern=None,
                 timeout=1, max_transitions=5)

        with self.assertRaises(condoor.ConnectionTimeoutError):
            sm.run()

    def test_fsm_event_not_list(self):
        """FSM: Test single event"""

        class Ctrl(object):
            logger = None
            hostname = "hostname"

            def expect(self, events, searchwindowsize, timeout):
                pass

        ctrl = Mock(spec=Ctrl)
        ctrl.expect.return_value = 0
        ctrl.counter = 0

        events = "STATE1"

        transitions = [
            ("STATE1", [0], -1, None, 1),
        ]

        sm = FSM("FSM", ctrl, events=events, transitions=transitions, init_pattern=None,
                 timeout=1, max_transitions=5)

        result = sm.run()
        self.assertEqual(True, result)

    def test_fsm_action_is_string(self):
        """FSM: Test action is string"""

        class Ctrl(object):
            logger = None
            hostname = "hostname"

            def expect(self, events, searchwindowsize, timeout):
                pass

        ctrl = Mock(spec=Ctrl)
        ctrl.expect.return_value = 0
        ctrl.counter = 0

        events = "STATE1"

        action1 = "not callable string"

        transitions = [
            ("STATE1", [0], -1, action1, 1),
        ]

        sm = FSM("FSM", ctrl, events=events, transitions=transitions, init_pattern=None,
                 timeout=1, max_transitions=5)

        with self.assertRaises(RuntimeWarning):
            sm.run()

    def test_fsm_action_is_class(self):
        """FSM: Test action is class"""

        class Ctrl(object):
            logger = None
            hostname = "hostname"

            def expect(self, events, searchwindowsize, timeout):
                pass

        ctrl = Mock(spec=Ctrl)
        ctrl.expect.return_value = 0
        ctrl.counter = 0
        ctrl.logger.setLevel(10)

        events = "STATE1"

        class action1:
            pass

        transitions = [
            ("STATE1", [0], -1, action1, 1),
        ]

        sm = FSM("FSM", ctrl, events=events, transitions=transitions, init_pattern=None,
                 timeout=1, max_transitions=5)

        with self.assertRaises(RuntimeWarning):
            sm.run()

    def test_fsm_action_is_partial(self):
        """FSM: Test action is partial"""

        class Ctrl(object):
            logger = None
            hostname = "hostname"

            def expect(self, events, searchwindowsize, timeout):
                pass

        ctrl = Mock(spec=Ctrl)
        ctrl.expect.return_value = 0
        ctrl.counter = 0

        events = ["STATE1"]

        @action
        def action1(value, ctx):
            self.assertEqual(value, "test_value")
            return True

        transitions = [
            ("STATE1", [0], -1, partial(action1, "test_value"), 1),
        ]

        sm = FSM("FSM", ctrl, events=events, transitions=transitions, init_pattern=None,
                 timeout=1, max_transitions=5)

        result = sm.run()
        self.assertTrue(result)

    def test_fsm_unknown_state(self):
        """FSM: Test unknown state transition"""

        class Ctrl(object):
            logger = None
            hostname = "hostname"

            def expect(self, events, searchwindowsize, timeout):
                pass

        ctrl = Mock(spec=Ctrl)
        ctrl.expect.return_value = 2
        ctrl.counter = 0

        events = "STATE1"

        transitions = [
            ("STATE1", [0], -1, action, 1),
        ]

        sm = FSM("FSM", ctrl, events=events, transitions=transitions, init_pattern=None,
                 timeout=1, max_transitions=5)

        result = sm.run()
        self.assertFalse(result)
