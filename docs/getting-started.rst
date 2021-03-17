Getting Started
===============

.. currentmodule:: nopdb

Capturing function calls
------------------------

The functions :func:`capture_call` and :func:`capture_calls` allow
capturing useful information about calls to a given function.
They are typically used as context managers, e.g.:

.. code-block:: python

    with nopdb.capture_call(fn) as call:
        some_code_that_calls_fn()

        print(call)  # see details about how fn() was called

.. Note:: Only calls to pure-Python functions can be captured. Built-in functions
   and C extensions are not supported.

To have a concrete example, let's first define some simple functions to work with:

.. code-block:: python

    >>> def f(x, y):
    ...     z = x + y
    ...     return 2 * z
    >>> def g(x):
    ...     return f(x, x)

Now let's try calling :code:`g()` and capturing the call to :code:`f()` that
will be made from there:

.. code-block:: python

    >>> with nopdb.capture_call(f) as call:
    ...     g(1)
    4
    >>> call
    CallCapture(name='f', args=OrderedDict(x=1, y=1), return_value=4)
    >>> call.args['x']
    1
    >>> call.return_value
    4
    >>> call.locals
    {'y': 1, 'x': 1, 'z': 2}
    >>> call.print_stack()
    File "<stdin>", line 2, in <module>
    File "<stdin>", line 2, in g
    File "<stdin>", line 1, in f

The object returned by :func:`capture_calls` will always contain information
about the *most recent* call within the context manager block.
To capture *all* the calls, we can use :func:`capture_calls` (in the plural):

.. code-block:: python

    >>> with nopdb.capture_calls(function=f) as calls:
    ...     g(1)
    ...     g(42)
    ...
    4
    168
    >>> calls
    [CallInfo(name='f', args=OrderedDict(x=1, y=1), return_value=4),
     CallInfo(name='f', args=OrderedDict(x=42, y=42), return_value=168)]

Both :func:`capture_call` and :func:`capture_calls` support different ways of
specifying which function(s) should be considered:

* We may pass a function or its name, i.e. :code:`capture_calls(f)` or
  :code:`capture_calls('f')`.
* A module, a filename or a full file path can be passed, e.g.
  :code:`capture_calls('f', module=mymodule)`
  or
  :code:`capture_calls('f', file='mymodule.py')`.
* Both functions may be called without arguments, meaning that *all*
  Python functions should be captured.


Setting breakpoints
-------------------


The :class:`NoPdb` class
------------------------