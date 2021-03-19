NoPdb: Non-interactive Python Debugger
======================================

Introduction
------------

NoPdb is a **programmatic** (non-interactive) **debugger** for Python. This means it gives you access to
**debugger-like superpowers** directly from your code. With NoPdb, you can:

* **capture function calls**, including arguments, local variables, return values and stack traces
* **set "breakpoints"** that trigger user-defined actions when hit, namely:

  * **evaluate expressions** to retrieve their values later
  * **execute arbitrary code**, including modifying local variables
  * **enter an interactive debugger** like `pdb`

.. Note:: NoPdb should run at least under CPython and PyPy. Most features should work under any implementation
  as long as it has :func:`sys.settrace()`.

Contents
--------

.. toctree::
  :hidden:
  :maxdepth: 2
  :caption: Contents

  Introduction <self>

.. toctree::
  :includehidden:
  :maxdepth: 2

  getting-started
  api
