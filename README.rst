NoPdb: Non-interactive Python Debugger
======================================

NoPdb is a **programmatic** (non-interactive) **debugger** for Python. This means it gives you access to
**debugger-like superpowers** directly from your code. With NoPdb, you can:

* **capture function calls**, including arguments, local variables, return values and stack traces
* **set "breakpoints"** that trigger user-defined actions when hit, namely:

  * **evaluate expressions** to retrieve their values later
  * **execute arbitrary code**, including modifying local variables
  * **enter an interactive debugger** like `pdb`

**Note:** This project is in its early development stage. Contributions and improvement ideas are welcome.

Capturing function calls
------------------------

The functions :code:`capture_call` and :code:`capture_calls` allow
capturing useful information about calls to a given function.
They are typically used as context managers, e.g.:

.. code-block:: python

    with nopdb.capture_calls(fn) as calls:
        some_code_that_calls_fn()

        print(calls)  # see details about how fn() was called

The information we can retrieve includes the function's arguments, return value, local variables and stack trace. For example:

.. code-block:: python

    >>> with nopdb.capture_call(f) as call:
    ...     g(1)
    >>> call
    CallCapture(name='f', args=OrderedDict(x=1, y=1), return_value=4)
    >>> call.print_stack()
    File "<stdin>", line 2, in <module>
    File "<stdin>", line 2, in g
    File "<stdin>", line 1, in f
    >>> call.args['x']
    1
    >>> call.return_value
    4
    >>> call.locals
    {'y': 1, 'x': 1, 'z': 2}

Setting breakpoints
-------------------

Like conventional debuggers, NoPdb can set breakpoints. However, because NoPdb is a
*non-interactive* debugger, its breakpoints do not actually stop the execution of the
program. Instead, they allow executing actions scheduled in advance, such as
evaluating expressions.

To set a breakpoint, call the :code:`breakpoint` function. A breakpoint object
is returned, allowing to schedule actions using its methods such as
:code:`eval()` and :code:`exec()`. For example:

.. code-block:: python

   # Break at line 3 of the file or notebook cell where f is defined
   with nopdb.breakpoint(function=f, line=3) as bp:
       x = bp.eval("x")             # Schedule an expression
       type_y = bp.eval("type(y)")  # Another one
       bp.exec("print(y)")          # Schedule a print statement

       some_code_that_calls_f()

   print(x, type_y)  # Retrieve the captured values

Not only can we capture values, we can also modify them!

.. code-block:: python

    >>> with nopdb.breakpoint(function=f, line=3) as bp:
    ...     # Get the value of x, then increment it, then get the new value
    ...     x_before = bp.eval('x')
    ...     bp.exec('x += 1')
    ...     x_after = bp.eval('x')
    ...
    ...     some_code_that_calls_f()
    >>> x_before
    [2]
    >>> x_after
    [3]