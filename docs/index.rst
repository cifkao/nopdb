Nopdb
========

Introduction
------------

Nopdb is a **programmatic debugger** for Python. This means it gives you access to
**debugger-like superpowers** directly from your code, without the hassle of starting
an actual debugger. With Nopdb, you can:

* **capture function calls**, including arguments, local variables and return values
* **set "breakpoints"** which do not actually stop the execution of the program, but
  can trigger **user-defined actions** when hit, namely:

  * **evaluate expressions** to retrieve their values later
  * **execute arbitrary code**, including modifying local variables
  * **enter an actual debugger** like `pdb`

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
