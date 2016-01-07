# =============================================================================
# fsm
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
    """This class represents Finite State Machine for the current device connection. Here is the
        example of usage::

            to be done


        The example action::

            def send_newline(ctx):
                ctx.ctrl.sendline()
                return True

            def error(ctx):
                ctx.message = "Filesystem error"
                return False

            def readonly(ctx):
                ctx.message = "Filesystem is readonly"
                return False

        The ctx object description refer to :class:`condoor.controllers.fsm.FSM`.

        If the action returns True then the FSM continues processing. If the action returns False then FSM stops
        and the error message passed back to the ctx object is posted to the log.


        The FSM state is the integer number. The FSM starts with initial ``state=0`` and finishes if the ``next_state``
        is set to -1.

        If action returns False then FSM returns False. FSM returns True if reaches the -1 state.

        """

    max_transitions = 20

    class Context(object):
        _slots__ = ['fsm_name', 'ctrl', 'event_index', 'event', 'state', 'finished', 'msg']
        fsm_name = "FSM"
        ctrl = None
        event_index = 0
        event = None
        state = 0
        finished = False
        msg = ""

        def __init__(self, fsm_name, ctrl):
            """This is a class constructor.

            Args:
                fsm_name (str): Name of the FSM. This is used for logging.
                ctrl (object): The controller object.
            """
            self.ctrl = ctrl
            self.fsm_name = fsm_name

        def __str__(self):
            """Returns the string representing the context"""
            return "FSM Context:E={},S={},FI={},M='{}'".format(
                self.event, self.state, self.finished, self.msg)

    def __init__(self, name, ctrl, events, transitions, init_pattern=None, timeout=300):
        """This is a FSM class constructor.

        Args:
            name (str): Name of the state machine used for logging purposes. Can't be *None*
            ctrl (object): Controller class representing the connection to the device
            events (list): List of expected strings or pexpect.TIMEOUT exception expected from the device.
            transitions (list): List of tuples in defining the state machine transitions.
            init_pattern (str): The pattern that was expected in the previous operation.
            timeout (int): Timeout between states in seconds. Defaults to 300 seconds.

        The transition tuple format is as follows::

            (event, [list_of_states], next_state, action, timeout)

        - event (str): string from the `events` list which is expected to be received from device.
        - list_of_states (list): List of FSM states that triggers the action in case of event occurrence.
        - next_state (int): Next state for FSM transition.
        - action (func): function to be executed if the current FSM state belongs to `list_of_states` and the `event`
          occurred. The action can be also *None* then FSM transits to the next state without any action. Action
          can be also the exception, which is raised and FSM stops.
        """
        self.events = events
        self.ctrl = ctrl
        self.timeout = timeout
        self.name = name
        self.init_pattern = init_pattern
        self.logger = logging.getLogger('condoor.fsm')

        self.transition_table = self._compile(transitions, events)

    def _compile(self, transitions, events):
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
        """This method starts the FSM.

            Returns:
                boolean: True if FSM reaches the last state or false if the exception or error message was raised
        """
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
                            self._dbg(50, "Error: {}".format(ctx.msg))
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
                    self._dbg(40, "Unknown transition: EVENT={},STATE={}".format(ctx.event, ctx.state))
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
