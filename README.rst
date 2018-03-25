=========
Apocrypha
=========

Apocrypha is a lightweight, flexible JSON server and client written in Python
3. It includes a client library for easy interaction through Python, but it's
simple query format allows APIs to easily written in other languages.

-----

A simple client in Bash

.. code-block:: shell
  #!/bin/bash

  while [[ $1 ]]; do
    echo "$1"
    shift
  done | nc localhost 9999

-----

Example Python usage

::
  
  $ python3 -m apocrypha.server

  $ python3
  >>> from apocrypha.client import Client
  >>> db = Client()
  >>> for i in range(0, 100):
  ...   db.append('numbers', value=i)
  ...
  >>> db.get('numbers')[:10]
  [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

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
