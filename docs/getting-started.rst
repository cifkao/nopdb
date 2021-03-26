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

.. doctest::

    >>> def f(x, y):
    ...     z = x + y
    ...     return 2 * z
    >>> def g(x):
    ...     return f(x, x)

Now let's try calling :code:`g()` and capturing the call to :code:`f()` that
will be made from there:

.. doctest::

    >>> with nopdb.capture_call(f) as call:
    ...     g(1)
    4
    >>> call
    CallCapture(name='f', args=OrderedDict(x=1, y=1), return_value=4)
    >>> call.args['x']
    1
    >>> call.return_value
    4
    >>> call.locals  # doctest: +SKIP
    {'x': 1, 'y': 1, 'z': 2}
    >>> call.print_stack()  # doctest: +SKIP
      File "<stdin>", line 2, in <module>
      File "<stdin>", line 2, in g
      File "<stdin>", line 1, in f

.. doctest::
    :hide:

    >>> call.locals == {'x': 1, 'y': 1, 'z': 2}
    True

The object returned by :func:`capture_calls` will always contain information
about the *most recent* call within the context manager block.
To capture *all* the calls, we can use :func:`capture_calls` (in the plural):

.. doctest::
    :options: +NORMALIZE_WHITESPACE

    >>> with nopdb.capture_calls(f) as calls:
    ...     g(1)
    ...     g(42)
    4
    168
    >>> calls
    [CallInfo(name='f', args=OrderedDict(x=1, y=1), return_value=4),
     CallInfo(name='f', args=OrderedDict(x=42, y=42), return_value=168)]

Both :func:`capture_call` and :func:`capture_calls` support different ways of
specifying which function(s) should be considered:

* We may pass a function or its name, i.e. :code:`capture_calls(f)` or
  :code:`capture_calls('f')`.
* Passing a method bound to an instance, as in :code:`capture_calls(obj.f)`,
  will work as expected: only calls invoked on that particular instance (and
  not other instances of the same class) will be captured.
* A module, a filename or a full file path can be passed, e.g.
  :code:`capture_calls('f', module=mymodule)`
  or
  :code:`capture_calls('f', file='mymodule.py')`.
* If no arguments are supplied, calls to *all* Python functions will be captured.


Setting breakpoints
-------------------

Like conventional debuggers, NoPdb can set breakpoints. However, because NoPdb is a
*non-interactive* debugger, its breakpoints do not actually stop the execution of the
program. Instead, they allow executing actions scheduled in advance, such as
evaluating expressions.

To set a breakpoint, call the :func:`breakpoint` function. A breakpoint object
is returned, allowing to schedule actions using its
:meth:`~Breakpoint.eval`, :meth:`~Breakpoint.exec` and :meth:`~Breakpoint.debug`
methods.

Using the example from the previous section, let's try to use a breakpoint to capture
the value of a variable:

.. doctest::

    >>> with nopdb.breakpoint(f, line=3) as bp:
    ...     z_values = bp.eval('z')  # Get the value of z whenever the breakpoint is hit
    ...
    ...     g(1)
    ...     g(42)
    4
    168
    >>> z_values
    [2, 84]

Not only can we capture values, we can also modify them!

.. doctest::

    >>> with nopdb.breakpoint(f, line=3) as bp:
    ...     # Get the value of z, then increment it, then get the new value
    ...     z_before = bp.eval('z')
    ...     bp.exec('z += 1')
    ...     z_after = bp.eval('z')
    ...
    ...     g(1)  # This would normally return 4
    6
    >>> z_before
    [2]
    >>> z_after
    [3]

.. Warning:: Assigning to local variables is somewhat experimental and only supported
    under CPython (the most common Python implementation) and PyPy.

The :class:`NoPdb` class
------------------------

Another way to use NoPdb is by creating a :class:`NoPdb` object. The object can either
be used as a context manager, or started and stopped explicitly using the
:meth:`~NoPdb.start` and :meth:`~NoPdb.stop` methods. This can be useful if we want to
set multiple breakpoints or call captures in a single context:

.. testcode::

    with nopdb.NoPdb():
        f_call = nopdb.capture_call(f)
        g_call = nopdb.capture_call(g)
        z_val = nopdb.breakpoint(f, line=3).eval('z')

        g(1)

.. doctest::
    :hide:

    >>> f_call
    CallCapture(name='f', args=OrderedDict(x=1, y=1), return_value=4)
    >>> g_call
    CallCapture(name='g', args=OrderedDict(x=1), return_value=4)
    >>> z_val
    [2]

Or alternatively:

.. testcode::

    dbg = nopdb.NoPdb()
    f_call = dbg.capture_call(f)
    g_call = dbg.capture_call(g)
    z_val = dbg.breakpoint(f, line=3).eval('z')

    dbg.start()
    g(1)
    dbg.stop()

.. doctest::
    :hide:

    >>> f_call
    CallCapture(name='f', args=OrderedDict(x=1, y=1), return_value=4)
    >>> g_call
    CallCapture(name='g', args=OrderedDict(x=1), return_value=4)
    >>> z_val
    [2]

.. Note:: While it is possible to create multiple :class:`NoPdb` objects, they cannot
    be active simultaneously. Starting a new instance will pause the currently active
    instance.
