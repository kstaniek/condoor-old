Core condoor components
=======================

.. automodule:: condoor

Connection class
----------------

.. autoclass:: Connection

   .. automethod:: __init__
   .. automethod:: discovery
   .. automethod:: connect
   .. automethod:: reconnect
   .. automethod:: disconnect
   .. automethod:: store_property
   .. automethod:: get_property
   .. automethod:: condoor.platforms.generic.Connection.reload
   .. automethod:: condoor.platforms.generic.Connection.send
   .. automethod:: condoor.platforms.generic.Connection.enable
   .. automethod:: condoor.platforms.generic.Connection.run_fsm

   .. autoattribute:: family
   .. autoattribute:: platform
   .. autoattribute:: os_type
   .. autoattribute:: hostname
   .. autoattribute:: prompt
   .. autoattribute:: is_connected

