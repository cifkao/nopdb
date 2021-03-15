Nopdb
========

Introduction
------------

Nopdb is a **programmatic debugger** for Python. This means it gives you access to
**debugger-like superpowers** directly from your code, without the hassle of starting
an actual debugger. With Nopdb, you can:

* **capture function calls**, including arguments, local variables and return values
* **place "breakpoints"** which do not actually stop the execution of the program, but
  allow **scheduling actions** that get performed when the breakpoint is hit, namely:

   * **evaluating expressions** to retrieve their values later
   * **executing arbitrary code**, including modifying local variables

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
