# =============================================================================
# fsm
#
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
from functools import wraps
from pexpect import EOF
from time import time

from ..exceptions import \
    ConnectionError


def action(func):
    @wraps(func)
    def with_logging(*args, **kwargs):
        for arg in args:
            if isinstance(arg, FSM.Context):
                logging.getLogger(__name__).debug("[{}]: [{}] A={}".format(
                    arg.ctrl.hostname, arg.fsm_name, func.__name__))
                break
        else:
            logging.getLogger(__name__).debug("[FSM] A={}".format(func.__name__))
        return func(*args, **kwargs)
    return with_logging


class FSM(object):
    max_transitions = 20

    class Context(object):
        _slots__ = ['ctrl', 'event', 'state', 'failed', 'finished', 'msg']
        fsm_name = "FSM"
        ctrl = None
        event_index = 0
        event = None
        state = 0
        failed = False
        finished = False
        msg = ""

        def __init__(self, fsm_name, ctrl):
            self.ctrl = ctrl
            self.fsm_name = fsm_name

        def __str__(self):
            return "FSM Context:E={},S={},FA={},FI={},M='{}'".format(
                self.event, self.state, self.failed, self.finished, self.msg)

    def __init__(self, name, ctrl, events, transitions, init_pattern=None, timeout=300):
        self.events = events
        self.ctrl = ctrl
        self.timeout = timeout
        self.name = name
        self.init_pattern = init_pattern
        self.logger = logging.getLogger(self.ctrl.hostname)

        self.transition_table = self.compile(transitions, events)

    def compile(self, transitions, events):
        compiled = {}
        for transition in transitions:
            event, states, new_state, action, timeout = transition
            if not isinstance(states, list):
                states = list(states)
            try:
                event_index = events.index(event)
            except ValueError:
                self._dbg(10, "Transition for non-existing event: {}".format(
                    event if isinstance(event, str) else event.pattern))
            else:
                for state in states:
                    key = (event_index, state)
                    compiled[key] = (new_state, action, timeout)

        return compiled

    def run(self):
        ctx = FSM.Context(self.name, self.ctrl)
        transition_counter = 0
        timeout = self.timeout
        self._dbg(10, "FSM Started")
        while transition_counter < self.max_transitions + 1:
            transition_counter += 1
            try:
                start_time = time()
                if self.init_pattern is None:
                    ctx.event = self.ctrl.expect(self.events, timeout=timeout)
                else:
                    if isinstance(self.init_pattern, str):
                        self._dbg(10, "INIT_PATTERN={}".format(self.init_pattern.encode('string_escape')))
                    elif self.init_pattern is not None:
                        self._dbg(10, "INIT_PATTERN={}".format(self.init_pattern.pattern.encode('string_escape')))
                    ctx.event = self.events.index(self.init_pattern)
                    self.init_pattern = None
                finish_time = time() - start_time
                key = (ctx.event, ctx.state)
                ctx.pattern = self.events[ctx.event]

                if key in self.transition_table:
                    transition = self.transition_table[key]
                    next_state, action, next_timeout = transition
                    self._dbg(10, "E={},S={},T={},RT={:.2f}".format(
                        ctx.event, ctx.state, timeout, finish_time))
                    if callable(action):
                        if not action(ctx):
                            self._dbg(10, "Error: {}".format(ctx.msg))
                            return False
                    elif isinstance(action, Exception):
                        raise action
                    elif action is None:
                        self._dbg(10, "No action")
                    else:
                        self._dbg(40, "FSM Action is not callable: {}".format(action.__name__))
                        raise Exception("FSM Action is not callable")

                    if next_timeout != 0:  # no change if set to 0
                        timeout = next_timeout
                    ctx.state = next_state
                    self._dbg(10, "NS={},NT={}".format(next_state, timeout))

                else:
                    self._dbg(10, "Unknown transition: EVENT={},STATE={}".format(ctx.event, ctx.state))
                    continue

            except EOF:
                raise ConnectionError("Session closed unexpectedly", self.ctrl.hostname)

            if ctx.finished or next_state == -1:
                self._dbg(10, "FSM finished at E={},S={}".format(ctx.event, ctx.state))
                return True

        else:  # check while else if even exists
            self._dbg(40, "FSM looped. Exiting")
            return False

    def _dbg(self, level, msg):
        self.logger.log(
            level, "[{}]: [{}] {}".format(self.ctrl.hostname, self.name, msg)
        )
