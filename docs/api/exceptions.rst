Exceptions
==========

This chapter describes all the exceptions used by condoor module.

.. automodule:: condoor.exceptions

.. autoclass:: GeneralError
   :show-inheritance:

   This is a base class for all exceptions raised by condoor module.

   .. automethod:: __init__


Connection exceptions
-----------------------------

The exceptions below are related to connection handling events. There are covered three cases:

- general connection errors caused by device disconnect or jumphosts disconnects,
- authentication errors caused by using wrong credentials to access the device,
- timeout errors caused by lack of response within defined amount of time.


.. autoclass:: condoor.exceptions.ConnectionError
   :show-inheritance:
.. autoclass:: condoor.exceptions.ConnectionAuthenticationError
   :show-inheritance:
.. autoclass:: condoor.exceptions.ConnectionTimeoutError
   :show-inheritance:

Command exceptions
------------------

The exceptions below are related to command execution. There are covered three cases:

- generic command execution error,
- command syntax error,
- command execution timeout.

.. autoclass:: condoor.exceptions.CommandError
   :show-inheritance:

   This is base class for command related exceptions which extends the standard message with a 'command' string
   for better user experience and error reporting.

   .. automethod:: __init__

.. autoclass:: condoor.exceptions.CommandSyntaxError
   :show-inheritance:
.. autoclass:: condoor.exceptions.CommandTimeoutError
   :show-inheritance:

URL exceptions
------------------
This exception is raised when invalid URL to the :class:`condoor.Connection` class is passed.

.. autoclass:: condoor.exceptions.InvalidHopInfoError
   :show-inheritance:
