#!/usr/bin/env python3

# pylint: disable=too-many-statements
# pylint: disable=too-many-branches
# pylint: disable=too-many-return-statements
# pylint: disable=too-many-instance-attributes

'''
Database and exception definitions
'''

import json
import pprint
import sys
import threading
import time
import zlib

from apocrypha.exceptions import DatabaseError


OPERATORS = {
    '=', '+', '-', '@', '-k', '--keys', '-e', '--edit', '-s',
    '--set', '-d', '--del', '-p', '--pop'}

READ_OPS = {
    '-e', '--edit', '-k', '--keys'}

WRITE_OPS = OPERATORS - READ_OPS


class Database(object):
    '''
    A flexible, json based database that supports
    - strings, lists, dictionaries
    - references to other keys
    - arbitrary depth indexing and assignment
    - symbolic links to other keys at any level
    '''

    def __init__(self, path: str, stateless: bool = False,
                 headless: bool = True) -> object:
        '''
        @path           full path to the database json file
        @stateless      never write out changes to disk
        @headless       don't write to stdout, save in self.output
        '''
        self.add_context = False
        self.dereference_occurred = False
        self.write_needed = False
        self.headless = headless
        self.path = path
        self.strict = False
        self.lock = threading.Lock()

        self.output = []    # list of string
        self.cache = {}     # dict of tuple of string

        self._queue_write = False

        try:
            with open(path, 'rb') as filep:
                data = filep.read()
                try:
                    data = zlib.decompress(data).decode()
                    self.data = json.loads(data)
                except zlib.error:
                    self.data = json.loads(data.decode())

        except FileNotFoundError:
            self.data = {}

        except ValueError:
            self._error('could not parse database on disk')

        self.writer_running = threading.Event()
        self.writer_running.set()
        self._writer_thread = threading.Thread(target=self._writer)
        if not stateless:
            self._writer_thread.start()

    def post_action(self) -> None:
        '''
        cache, normalize, queue a disk write, reset internal values
        '''
        self._normalize(self.data)

        if self.write_needed:
            self.cache = {}
            self._queue_write = True

        # reset
        self.add_context = False
        self.dereference_occurred = False
        self.output = []
        self.strict = False
        self.write_needed = False

    def action(self, args: [str]) -> None:
        '''
        may be overridden for custom behavior such as utilizing self.cache or
        '''
        self._action(self.data, args)

    def _maybe_cache(self, args: [str]) -> None:
        '''
        check if we can cache the input and output of this query
        '''
        key = tuple(args)

        # do not cache if context was added, a dereference was required to
        # get the result or the query contained a write operator
        cache = not (self.add_context or self.dereference_occurred)
        cache = cache and not WRITE_OPS.intersection(set(args))

        if cache:
            self.cache[key] = self.output

    def _writer(self) -> None:
        '''
        callback for writer_thread
        '''
        while self.writer_running.is_set():
            time.sleep(1)

            if self._queue_write:

                # write the updated values back out
                with open(self.path, 'wb') as filep:
                    data = json.dumps(self.data, separators=(',', ':'))
                    filep.write(zlib.compress(data.encode()))

                self._queue_write = False

    def _normalize(self, data: dict) -> bool:
        '''
        @data     level of the database to normalize

        Finds lists of a single element and converts them into singletons,

        deletes key that don't have values, returns true when a child was
        deleted so the parent knows to recheck itself

        this allows deeply nested dictionarys not ending in a value to be
        removed in one call to normalize() on the root of the database

            { a : { b : { c : {} } } } -> None
        '''

        child_removed = False

        for child, leaf in list(data.items()):

            # remove children without leaves
            if not leaf:
                del data[child]
                child_removed = True

            type_of_leaf = type(leaf)

            # convert lists of a single element to singletons
            if type_of_leaf == list and len(leaf) == 1:
                data[child] = leaf[0]

            # recurse
            elif type_of_leaf == dict:
                child_removed_child = self._normalize(leaf)

                # if our child removed a child, they may now need to be removed
                # if that was their only child; so we check ourselves again
                if child_removed_child:
                    return self._normalize(data)

        return child_removed

    def _error(self, message: str) -> None:
        '''
        @message    description of the error that occurred
        #impure     self.output

        Send an error to the user and stop execution. In headless mode, errors
        are appended to the class.output list
        '''
        message = 'error: ' + message

        if self.headless:
            self.output += [message]
            raise DatabaseError(message + '\n')

        print(message, file=sys.stderr)
        sys.exit(1)

    def _action(self, base: dict, keys: [str]) -> None:
        '''
        @base   current level of the database
        @keys   keys or arguments to apply

        Move through the input arguments to
            - index further into the database
            - delete keys
            - assign values to keys
        '''
        last_base = {}

        for i, key in enumerate(keys):
            left = keys[i - 1]      # string
            right = keys[i + 1:]    # list of string

            if key in OPERATORS:
                if key == '=':
                    self._assign(last_base, left, right)
                    return

                elif key == '+':
                    self._append(last_base, left, right)
                    return

                elif key == '-':
                    self._remove(last_base, left, right)
                    return

                elif key == '@':
                    self._search(self.data, keys[i + 1], keys[:i])
                    return

                elif key in {'-k', '--keys'}:
                    self._keys(base, left)
                    return

                elif key in {'-e', '--edit'}:
                    self.output = [json.dumps(base, indent=4, sort_keys=True)]
                    return

                elif key in {'-s', '--set'}:
                    self._set(last_base, left, right[0])
                    return

                elif key in {'-d', '--del'}:
                    del last_base[left]
                    self.write_needed = True
                    return

                elif key in {'-p', '--pop'}:
                    self._pop(last_base, left)
                    return

            # indexing

            # keep track of the level before so we can modify this level
            last_base = base

            try:
                key_is_reference = False
                base_is_reference = False

                if key[0] == '!':
                    key = key[1:]
                    key_is_reference = True

                if base[0] == '!':
                    base = base[1:]
                    base_is_reference = True

            except (IndexError, KeyError):
                pass

            try:
                if base_is_reference:
                    # we're rebasing ourselves on the dereferenced value of
                    # our current base. we keep all arguments
                    #
                    # this means that we're trying to index through a
                    # reference
                    self._dereference(base, keys[i:])
                    return

                base = base[key]

                if key_is_reference:
                    # this means we're trying to get the value of a reference
                    self._dereference(base, right)
                    return

            except KeyError:
                if self.strict:
                    self._error(key + ' not found')

                # create a new key, if unused, it'll be cleaned by normalize()
                base[key] = {}
                base = base[key]

            except TypeError:
                self._error(
                    'cannot index through non-dict.'
                    ' {a} -> {b} -> ?, {a} :: {t}'
                    .format(a=left, b=key, t=type(base).__name__))

        self._display(base, context=' = '.join(keys[:-1]))

    def _dereference(self, base: dict, args: [str]) -> None:
        '''
        @base   current object that we're working with, corresponds to a
                "level" in the database
        @args   list of database keys to check

        Dereferences always start at the top level of the database, hence the
            action(data, data, ...)

            $ d pointer = value
            $ d !pointer
            value

        Spaces are significant in value being treated as references. A space
        denotes a new level of indexing from the top level

            $ d pointer = 'one two'
            $ d one two = value
            $ d !pointer
            value
        '''
        self.dereference_occurred = True

        # current value is a string
        if isinstance(base, str):
            if base in self.data:
                target = [base]
            else:
                target = base.split(' ')

            self._action(
                self.data, target + args)

        # current value is iterable
        else:
            for reference in base:

                if reference in self.data:
                    target = [reference]
                else:
                    target = reference.split(' ')

                self._action(self.data, target + args)

    def _display(self, value: any, context: str = None) -> None:
        '''
        @value      string, list or dict to add to output
        @context    additional information to include in output

        Figure out what a value is, and print it correctly, dereferences
        symlinks automatically
        '''
        if not value:
            return

        result, base = [], ''

        if context and self.add_context:
            base = context + ' = '

        # string
        if isinstance(value, str):
            if value[0] == '!':
                value = value[1:]
                self._dereference(value, [])
            else:
                result += [base + str(value)]

        # list
        elif isinstance(value, list):
            for elem in value:
                if elem and isinstance(elem, str) and elem[0] == '!':
                    elem = elem[1:]
                    self._dereference(elem, [])
                else:
                    result += [base + str(elem)]

        # dict
        else:
            result += [base + pprint.pformat(value)]

        self.output += result

    def _search(self, base: dict, target: str, context: [str]) -> None:
        '''
        @base       the object to search through
        @key        value to find
        @context    additional information to pass onto _display()

        Recursively search through the base dictionary, print out all the keys
        that have the given value '''

        self.add_context = True

        # list
        if isinstance(base, list):
            if target in base:
                self._display(target, context=' '.join(context))
            return

        # dict
        for key, value in base.items():
            if target == value:
                self._display(target, context=' '.join(context + [key]))

            elif target == key:
                self._display(target, context=' '.join(context))

            elif isinstance(value, (dict, list)):
                self._search(value, target, context + [key])

    def _assign(self, base: dict, left: str, right: [str]) -> None:
        '''
        direct assignment, right side may be a list or string
        '''
        # single = string, multi = list
        right = right[0] if len(right) == 1 else right

        if base[left] == right:
            return

        base[left] = right
        self.write_needed = True

    def _append(self, base: dict, left: str, right: [str]) -> None:
        '''
        append a value or values to a list or string
        may create a new value
        '''
        ltype = type(base[left])

        # creation of a new value
        if not base[left]:
            base[left] = right[0] if len(right) == 1 else right

        # attempt to append to dictionary, error
        elif ltype == dict:
            self._error('cannot append to a dictionary')

        # left and right are lists
        elif ltype == list:
            base[left] += right

        # value exists but is a singleton, create list and add
        else:
            base[left] = [base[left]] + right

        self.write_needed = True

    def _keys(self, base: dict, left: str) -> None:
        '''
        print the keys defined at this level
        '''
        if not isinstance(base, dict):
            self._error(
                'cannot retrieve keys non-dict. {a} :: {t}'
                .format(a=left, t=type(base).__name__))

        self._display(sorted(base.keys()))

    def _set(self, base: dict, left: str, right: str) -> None:
        '''
        @base  current level of the database
        @left  index to modify
        @right new value of the index, as a JSON string

        set the entire sub tree for this value with JSON
        '''
        try:
            right = json.loads(right)

        except ValueError:
            self._error('malformed json')

        if base:
            if base[left] == right:
                return
            base[left] = right
        else:
            # global overwrite
            if isinstance(right, dict):
                self.data = right
            else:
                self._error('top level must be of type dict')

        self.write_needed = True

    def _remove(self, base: dict, left: str, right: [str]) -> None:
        ''' dict of any, string, list of string

        @base  current level of the database
        @left  index to modify
        @right elements to remove from left

        remove all elements in the right from the left
        '''
        if left not in base:
            self._error('{a} not in top level.'.format(a=left))

        # list
        if isinstance(base[left], list):
            for item in right:
                if item not in base[left]:
                    self._error('{a} not in {b}.'.format(a=item, b=left))

                base[left].remove(item)

            if len(base[left]) == 1:
                base[left] = base[left][0]

        # dict
        elif isinstance(base[left], dict):
            for item in right:
                if item not in base[left]:
                    self._error('{a} not in {b}.'.format(a=item, b=left))

                del base[left][item]

        # singleton
        else:
            for item in right:
                if item != base[left]:
                    self._error('{a} not in {b}.'.format(a=item, b=left))

                del base[left]

        self.write_needed = True

    def _pop(self, base: dict, left: str) -> None:
        '''
        display the result then remove it atomically
        '''
        if not base[left]:
            return

        elif isinstance(base[left], list):
            self._display(base[left].pop())
            self.write_needed = True

        # dict, str, int, ...
        else:
            self._display(base[left])
            del base[left]
            self.write_needed = True
