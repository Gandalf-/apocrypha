# Apocrypha
A flexible JSON database that supports a wide variety of operations. Start the database server with `python3 -m apocrypha_server`. `bin/d` is the default client. You can connect to remote servers using `d` with the `-h` or `--host` flag. It will remember the last argument as the default server until you provide it again.

The following are the supported database operations:

### index

  index further into the database through a key, then recursively display all
  keys and values under the key. this is the usual way to traverse the database and gather information
```
  (dict a, str b, b in a) => a b -> IO

  $ d apples granny = good
  $ d apples
  {'granny': 'good'}
  $ d apples granny
  good
```

### +

  append a list or string to an existing string or list. create the left side
  if it doesn't already exist
```
  (none a | str a | list a, str b | list b) => a + b -> none | error

  $ d toppings = mushrooms
  $ d toppings + pineapple
  $ d toppings
  mushrooms
  pineapple
```

### -
  remove one or more elements from a list. if the resulting list now only
  contains one element, it's converted to a singleton
```
  (list a, str b | list b, b in a) => a - b -> none | error

  $ d sweets = cake pie pizza
  $ d sweets - pizza
  $ d sweets
  cake
  pie
```

### =
  assign the value of an element. if multiple arguments are given on the
  right side of the assignment, the result is list assignment
```
  (any a, str b | list b) => a = b -> none

  $ d apple = sauce pie
  $ d apple
  sauce
  pie
```

### @
  recursively search the current level for a value. displays all the keys
  that correspond have the value's value
```
  (str a) => IO

  $ d rasp = berry
  $ d blue = berry
  $ d @ berry
  rasp
  blue
```
### -k, --keys
  show the keys immediately under this value. doesn't recursively print all
  keys and values underneathe
```
  dict a => a --keys -> IO | error

  $ d stone sand = weak
  $ d stone lime = tough
  $ d stone --keys
  sand
  lime
```
### -s, --set
  replace the value of an index with raw JSON
```
  (any a, str b, JSON b) => a --set b -> none | error

  $ d pasta --set '["spaghetti", "lasgna"]'
  $ d pasta
  spaghetti
  lasagna
```
### -e, --edit
  dump the raw JSON value of a key. used by a client to allow modification in
  an editor and placement back in the database with --set
```
  any a => a --edit -> IO

  $ d pasta = spaghetti
  $ d pasta --edit
```
### -d, --del
  delete any element from it's parent dictionary
```
  any a => a --del -> none

  $ d apple sauce = good
  $ d apple pie = great
  $ d apple sauce --del
  $ d apple
  {'pie': 'great'}
```
