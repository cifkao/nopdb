NoPdb: Non-interactive Python Debugger
======================================

Introduction
------------

NoPdb is a **programmatic** (non-interactive) **debugger** for Python. This means it gives you access to
**debugger-like superpowers** directly from your code. With NoPdb, you can:

* **capture function calls**, including arguments, local variables and return values
* **set "breakpoints"** which do not actually stop the execution of the program, but
  can trigger **user-defined actions** when hit, namely:

  * **evaluate expressions** to retrieve their values later
  * **execute arbitrary code**, including modifying local variables
  * **enter an interactive debugger** like `pdb`

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

   api
