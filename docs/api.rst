API Reference
-------------
.. currentmodule:: nopdb

.. autofunction:: capture_call

.. autofunction:: capture_calls

.. autofunction:: breakpoint

.. autofunction:: get_nopdb

.. autoclass:: NoPdb
    :members:
    :undoc-members:

.. autoclass:: Breakpoint
    :members:
    :undoc-members:
    :show-inheritance:

    .. automethod:: enable

       Enable the breakpoint again after calling :meth:`disable`.

    .. automethod:: disable

       Disable (remove) the breakpoint.

.. autoclass:: Scope

.. autoclass:: CallInfo
    :members:
    :undoc-members:

.. autoclass:: CallCapture
    :members:
    :undoc-members:
    :show-inheritance:

    .. automethod:: enable

       Start capturing again after calling :meth:`disable`.

    .. automethod:: disable

       Stop capturing.

.. autoclass:: CallListCapture
    :members:
    :undoc-members:
    :show-inheritance:

    .. automethod:: enable

       Start capturing again after calling :meth:`disable`.

    .. automethod:: disable

       Stop capturing.
