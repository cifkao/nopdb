NoPdb: Non-interactive Python Debugger
======================================
|pypi-package| |docs-status| |test-status| |lint-status|

* **Installation:** :code:`pip install nopdb`
* **Docs:** https://nopdb.readthedocs.io/

NoPdb is a **programmatic** (non-interactive) **debugger** for Python. This means it gives you access to
**debugger-like superpowers** directly from your code. With NoPdb, you can:

* **capture function calls**, including arguments, local variables, return values and stack traces
* **set "breakpoints"** that trigger user-defined actions when hit, namely:

  * **evaluate expressions** to retrieve their values later
  * **execute arbitrary code**, including modifying local variables
  * **enter an interactive debugger** like `pdb`

NoPdb is also a convenient tool for inspecting **machine learning model internals**. For example,
`this notebook <https://colab.research.google.com/github/cifkao/nopdb/blob/main/docs/pytorch_tutorial.ipynb>`_ 
and `this post on Towards Data Science <https://towardsdatascience.com/dissecting-ml-models-with-nopdb-6ff4651fb131>`__
show how to use it to visualize Transformer attention in PyTorch.

NoPdb should run at least under CPython and PyPy. Most features should work under any implementation
as long as it has :code:`sys.settrace()`.

**Note:** This project is in its early development stage. Contributions and improvement ideas are welcome.

Capturing function calls
------------------------

The functions :code:`capture_call()` and :code:`capture_calls()` allow
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

To set a breakpoint, call the :code:`breakpoint()` function. A breakpoint object
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

There are other ways to specify the breakpoint location. For example:

.. code-block:: python

   # Break at any line with the given source code in the given file
   with nopdb.breakpoint(file="pathlib.py", line="return obj") as bp:
       ...

   # Break as soon as any function with the given name is called
   with nopdb.breakpoint(function="myfunc") as bp:
       ...

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

Planned features
----------------
Functionalities that do not exist, but could be added in the future:

* :code:`Breakpoint.callback()` for calling a given callback function, passing information about the current frame as an argument.
* :code:`Breakpoint.jump()` for jumping to a different line in the same function.
* A way to disable breakpoints.

Limitations
-----------

* Like Pdb, NoPdb only works with pure-Python functions. Calls to built-ins and C extensions cannot be captured. This also applies to ML frameworks that compile models into static graphs; for NoPdb to work, this feature needs to be disabled, e.g. with :code:`tf.config.run_functions_eagerly(True)` in TensorFlow and with the :code:`jax.disable_jit()` context manager in JAX.
* Local variable assignment in :code:`Breakpoint.exec()` is only supported under CPython and PyPy.

.. |pypi-package| image:: https://badge.fury.io/py/nopdb.svg?
   :target: https://pypi.org/project/nopdb/
   :alt: PyPI Package
.. |docs-status| image:: https://readthedocs.org/projects/nopdb/badge/?version=latest
   :target: https://nopdb.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status
.. |test-status| image:: https://github.com/cifkao/nopdb/actions/workflows/test.yml/badge.svg
   :target: https://github.com/cifkao/nopdb/actions/workflows/test.yml
   :alt: Lint Status
.. |lint-status| image:: https://github.com/cifkao/nopdb/actions/workflows/lint.yml/badge.svg
   :target: https://github.com/cifkao/nopdb/actions/workflows/lint.yml
   :alt: Lint Status
