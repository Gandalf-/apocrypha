=========
Apocrypha
=========

.. image:: https://img.shields.io/pypi/v/apocrypha.svg
   :target: https://pypi.python.org/pypi/apocrypha
   :alt: PyPI Version

.. image:: https://img.shields.io/pypi/pyversions/apocrypha.svg
   :target: https://pypi.python.org/pypi/apocrypha
   :alt: Supported Python Versions

.. image:: https://travis-ci.org/Gandalf-/apocrypha.svg?branch=master
    :target: https://travis-ci.org/Gandalf-/apocrypha

.. image:: https://codecov.io/gh/Gandalf-/apocrypha/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/Gandalf-/apocrypha

Apocrypha is a lightweight, flexible JSON server and client written in Python
3. It includes a client library for easy interaction through Python, and it's
simple query format allows APIs to easily written in other languages.

You can install Apocrypha with pip: ``pip3 install apocrypha``

Then you're ready to start the server: ``python3 -m apocrypha.server``

Features
========

- **multithreaded** Thread safe server and client. All queries are atomic.

- **caching** Writes clear the cache, any query will be served out of the
  cache if possible.

- **nosql** No schemas, no overhead, just your data in the format you
  provided.

- **json** Serve any existing JSON file to the network or start from
  scratch. Supports unlimited nested dictionaries.

- **fast** Serve up to 20,000 queries per second on cache hit heavy workloads.
  Database is kept in memory, no disk reads are made after startup.

- **persistance** Writes are queued and saved to disk once per second.

- **lightweight** Less than 2,000 lines of Python and no external dependencies
  outside of the standard library.

-----

Example Python API usage, check ``pydoc3 apocrypha.client`` for full usage and
more examples.

.. code-block:: python
  
  from apocrypha.client import Client
  db = Client()
  
  # apocrypha supports lists, strings, and dictionaries
  for i in range(0, 100):
    db.append('numbers', value=i)
  
  print(db.get('numbers')[:10])

  # nested dictionaries are allowed!
  customers = {
    'alice': {
      'age': 30
    },
    'bob' : {
      'age': 20
    }
  }

  db.set('customers', value=customers)
  print(db.keys('customers'))

  # query for sub keys with a simple syntax
  print(db.get('customers', 'alice', 'age'))

  for customer in db.keys('customers'):
    print(db.get('customers', customer, 'age'))

-----

A simple C client is available here_ if you want faster start up times than
Python for client applications, like shell scripts.

.. _here: https://github.com/Gandalf-/DotFiles/blob/master/bin/d.c

The network protocol is simple: send the length of the message in bytes, then
the message. Query elements are delimited by newlines. Each message ends in a
newline, and newlines are included in the length calculation of the message.


index
=====

index further into the database through a key, then recursively display all
keys and values under the key. this is the usual way to traverse the database
and gather information

::

  (dict a, str b, b in a) => a b -> IO

  $ d apples granny = good
  $ d apples
  {'granny': 'good'}
  $ d apples granny
  good

append
======

append a list or string to an existing string or list. create the left side if
it doesn't already exist

::

  (none a | str a | list a, str b | list b) => a + b -> none | error

  $ d toppings = mushrooms
  $ d toppings + pineapple
  $ d toppings
  mushrooms
  pineapple


remove
======

remove one or more elements from a list. if the resulting list now only
contains one element, it's converted to a singleton

::

  (list a, str b | list b, b in a) => a - b -> none | error

  $ d sweets = cake pie pizza
  $ d sweets - pizza
  $ d sweets
  cake
  pie

assign
======

assign the value of an element. if multiple arguments are given on the right
side of the assignment, the result is list assignment

::

  (any a, str b | list b) => a = b -> none

  $ d apple = sauce pie
  $ d apple
  sauce
  pie

search
======

recursively search the current level for a value. displays all the keys that
correspond have the value's value

::

  (str a) => IO

  $ d rasp = berry
  $ d blue = berry
  $ d @ berry
  rasp
  blue

keys
====

show the keys immediately under this value. doesn't recursively print all keys
and values underneathe

::

  dict a => a --keys -> IO | error

  $ d stone sand = weak
  $ d stone lime = tough
  $ d stone --keys
  sand
  lime

set
===

replace the value of an index with raw JSON

::

  (any a, str b, JSON b) => a --set b -> none | error

  $ d pasta --set '["spaghetti", "lasgna"]'
  $ d pasta
  spaghetti
  lasagna

edit
====

dump the raw JSON value of a key. 

::

  any a => a --edit -> IO

  $ d pasta = spaghetti sauce
  $ d pasta --edit
  '["spaghetti", "sauce"]'

delete
======

delete any element from it's parent dictionary

::

  any a => a --del -> none

  $ d apple sauce = good
  $ d apple pie = great
  $ d apple sauce --del
  $ d apple
  {'pie': 'great'}
