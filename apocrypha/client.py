#!/usr/bin/env python3

# pylint: disable=too-many-arguments

'''
Client connection wrapper and network functions
'''

import json
import select
import socket
import subprocess
import sys
import threading
import time

from apocrypha.exceptions import DatabaseError
from apocrypha.network import read, write


class Client(object):
    '''
    client API object for communicating with an Apocrypha Server

    >>> db = apocrypha.client.Client()
    '''

    def __init__(self, host='localhost', port=9999):
        self.host = host
        self.port = port
        self.sock = None
        self.lock = threading.Lock()

    def query(self, keys, interpret=False):
        ''' list of str, maybe bool -> str | none

        uses a lock because multiple threads may be using the same Client
        object. the network protocol easily gets confused if the messages don't
        match the lengths sent before
        '''

        with self.lock:
            result, self.sock = _query(
                keys, self.host, port=self.port, interpret=interpret,
                close=False, sock=self.sock)

        return result

    def get(self, *keys, default=None, cast=None):
        ''' str ..., maybe any, maybe any -> any | DatabaseError

        retrieve a given key, if the key is not found `default` will be
        returned instead

        >>> values = db.get('nonexistant', 'index', default={})
        >>> type(values)
        dict

        >>> values = db.get('index', 'that', 'exists', cast=set)
        >>> type(values)
        set
        '''
        keys = list(keys) if keys else ['']
        result = self.query(keys, interpret=True)

        if not result:
            return default

        elif cast:
            try:
                if not isinstance(result, (list, dict,)):
                    result = [result]
                return cast(result)

            except ValueError:
                raise DatabaseError(
                    'error: unable to case to ' + str(cast)) from None

        else:
            return result

    def keys(self, *keys):
        ''' str ..., maybe any -> list of str | none | DatabaseError

        >>> keys = db.keys('devbot', 'events')
        >>> type(keys)
        list
        '''
        keys = list(keys) if keys else ['']
        result = self.query(keys + ['--keys'])
        return result if result else []

    def delete(self, *keys):
        ''' str ... -> none

        >>> db.delete('some', 'key')
        '''
        keys = list(keys) if keys else ['']
        self.query(keys + ['--del'])

    def pop(self, *keys, cast=None):
        ''' str ... -> any | None
        '''
        keys = list(keys) if keys else ['']

        result = self.query(keys + ['--pop'])
        result = result[0] if result else None

        try:
            if result and cast:
                result = cast(result)

        except ValueError:
            raise DatabaseError(
                'error: cast {c} is not applicable to {t}'
                .format(c=cast.__name__, t=result)) from None

        return result

    def append(self, *keys, value):
        ''' str ..., str | list of str -> none | DatabaseError

        append an element to an apocrypha list. appending to a str creates a
        list with the original element and the new element

        >>> db.append('new key', value='hello')
        >>> type(db.get('new key'))
        str
        >>> db.append('new key', value='there')
        >>> type(db.get('new key'))
        list
        '''
        keys = list(keys) if keys else ['']

        if isinstance(value, str):
            value = [value]

        try:
            self.query(keys + ['+'] + value)

        except (TypeError, ValueError):
            raise DatabaseError('error: {v} is not a str or list') from None

    def remove(self, *keys, value):
        ''' str ..., str | list of str -> none | DatabaseError

        remove an element from a list, if more than one of the element exists
        in the list, only one is removed

        >>> db.set('my', 'list', value=['a', 'b', 'c'])
        >>> db.remove('my', 'list', value='b')
        '''
        keys = list(keys) if keys else ['']

        if isinstance(value, str):
            value = [value]

        if not isinstance(value, (str, list)):
            raise DatabaseError('error: {v} is not a str or list') from None

        self.query(keys + ['-'] + value)

    def set(self, *keys, value):
        ''' str ..., str | list | dict | none -> none

        set a value for a given key, creating if necessary. can be used to
        delete keys if value={}

        >>> events = {'key': 'value'}
        >>> db.set('devbot', 'events', value=events)
        >>> db.get('devbot', 'events')
        {'key': 'value'}
        '''
        keys = list(keys) if keys else ['']

        try:
            value = json.dumps(value)
            self.query(keys + ['--set', value])

        except (TypeError, ValueError):
            raise DatabaseError(
                'error: value is not JSON serializable') from None

    def apply(self, *keys, func):
        ''' str ..., (list of any -> list of any) -> none

        >>> db.set('colors', value=['blue', 'green', 'red', 'red'])
        >>> db.apply('colors', func=lambda xs: list(set(xs)))
        >>> db.get('colors')
        ['blue', 'green', 'red']
        '''
        keys = list(keys) if keys else ['']

        values = func(self.get(*keys))
        self.set(*keys, value=values)


def query(args, host='localhost', port=9999, interpret=False):
    ''' list of str, str, int, bool -> any
    legacy wrapper around _query for backwards compatibility, we just throw
    away the socket
    '''
    result, _ = _query(args, host=host, port=port, interpret=interpret)
    return result


def _query(args, host='localhost', port=9999, interpret=False,
           close=True, sock=None):
    ''' list of str, str, int, bool, bool, bool -> any

    the real query function, all the others are wrappers

    send a query to an Apocrypha server, either returning a list of strs or
    the result of json.loads() on the result
    '''

    args = list(args)
    remote = (host, port)

    if interpret and args and args[-1] not in {'-e', '--edit'}:
        args += ['--edit']
    message = '\n'.join(args) + '\n'

    # if they didn't give us a socket create a new one
    if not sock:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(remote)

    # send the message, get the reply using apocrypha.network calls
    write(sock, message)
    result, error = read(sock)

    if error:
        raise DatabaseError('error: network length')
    if close:
        sock.close()

    result = list(filter(None, result.split('\n')))
    if result and result[0].startswith('error: '):
        raise DatabaseError(result[0]) from None

    if interpret:
        result = json.loads(''.join(result)) if result else None

    return result, sock


def _edit_temp_file(temp_file):
    ''' str -> str

    open up the result of the query in a temporary file for manual editing.
    '''
    subprocess.call(['vim', temp_file])

    with open(temp_file, 'r') as filep:
        output = filep.read()

    try:
        output = json.dumps(json.loads(output))

    except ValueError:
        print('error: file has JSON formatting errors')
        time.sleep(1)
        _edit_temp_file(temp_file)

    else:
        return output


def main(args):
    ''' list of str -> IO
    '''

    host = 'localhost'
    port = 9999

    # check for data in stdin
    if select.select([sys.stdin], [], [], 0.0)[0]:
        args += [sys.stdin.read()]

    # using a non local server
    if len(args) > 2 and args[0] in {'-h', '--host'}:
        host = args[1]
        args = args[2:]

    # using a non standard port
    if len(args) > 2 and args[0] in {'-p', '--port'}:
        port = int(args[1])
        args = args[2:]

    # check for edit mode before we make the query
    edit_mode = False
    if args and args[-1] in {'-e', '--edit'}:
        edit_mode = True
        temp_file = '/tmp/apocrypha-' + '-'.join(args[:-1]) + '.json'

    client = Client(host=host, port=port)
    result = client.get(*args)

    # interactive edit
    if edit_mode:
        with open(temp_file, 'w+') as filep:
            filep.write(
                json.dumps(result, indent=4, sort_keys=True))

        output = _edit_temp_file(temp_file)
        client.query(args[:-1] + ['--set', output])

    # result to console
    else:
        print(result)


if __name__ == '__main__':
    main(sys.argv[1:])
