Exceptions
==========

This chapter describes all the exceptions used by condoor module.

.. automodule:: condoor

.. autoexception:: GeneralError
   :show-inheritance:

   This is a base class for all exceptions raised by condoor module.

   .. automethod:: __init__


Connection exceptions
-----------------------------

The exceptions below are related to connection handling events. There are covered three cases:

- general connection errors caused by device disconnect or jumphosts disconnects,
- authentication errors caused by using wrong credentials to access the device,
- timeout errors caused by lack of response within defined amount of time.


.. autoexception:: condoor.ConnectionError

   Bases: :class:`condoor.GeneralError`

.. autoexception:: condoor.ConnectionAuthenticationError

   Bases: :class:`condoor.ConnectionError`

.. autoexception:: condoor.ConnectionTimeoutError

   Bases: :class:`condoor.ConnectionError`

Command exceptions
------------------

The exceptions below are related to command execution. There are covered three cases:

- generic command execution error,
- command syntax error,
- command execution timeout.

.. autoexception:: condoor.CommandError

   This is base class for command related exceptions which extends the standard message with a 'command' string
   for better user experience and error reporting.

   Bases: :class:`condoor.GeneralError`

   .. automethod:: __init__

.. autoexception:: condoor.CommandSyntaxError

   Bases: :class:`condoor.CommandError`

.. autoexception:: condoor.CommandTimeoutError

   Bases: :class:`condoor.CommandError`

URL exceptions
--------------
This exception is raised when invalid URL to the :class:`condoor.Connection` class is passed.

.. autoexception:: condoor.InvalidHopInfoError

   Bases: :class:`condoor.GeneralError`


Pexpect exceptions
------------------
Those are exceptions derived from pexpect module. This exception is used in FSM and :meth:`condoor.Connection.run_fsm`

.. autoexception:: condoor.TIMEOUT
   :show-inheritance:

