#!/usr/bin/env python3

import json
import select
import socket
import subprocess
import struct
import sys
import time

from apocrypha.core import ApocryphaError


class Client(object):
    '''
    client API object for communicating with an Apocrypha Server

    >>> db = apocrypha.client.Client()
    '''

    def __init__(self, host='localhost', port=9999):
        self.host = host
        self.port = port
        self.sock = None

    def _query(self, keys, raw=False):

        result, self.sock = query(
            keys, self.host, port=self.port, raw=raw,
            close=False, sock=self.sock)

        return result

    def get(self, *keys, default=None, cast=None):
        ''' string ..., maybe any, maybe any -> any | ApocryphaError

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
        result = self._query(keys, raw=True)

        if not result:
            return default

        elif cast:
            try:
                if isinstance(result, str):
                    result = [result]
                return cast(result)

            except ValueError:
                raise ApocryphaError(
                    'error: unable to case to ' + str(cast)) from None

        else:
            return result

    def keys(self, *keys):
        ''' string ..., maybe any -> list of string | none | ApocryphaError

        >>> keys = db.keys('devbot', 'events')
        >>> type(keys)
        list
        '''
        keys = list(keys) if keys else ['']
        result = self._query(keys + ['--keys'])
        return result if result else []

    def delete(self, *keys):
        ''' string ... -> none

        >>> db.delete('some', 'key')
        '''
        keys = list(keys) if keys else ['']
        self._query(keys + ['--del'])

    def pop(self, *keys, cast=None):
        ''' string ... -> any | None
        '''
        keys = list(keys) if keys else ['']

        result = self._query(keys + ['--pop'])
        result = result[0] if result else None

        try:
            if result and cast:
                result = cast(result)
        except ValueError:
            print('error', keys, result)
            raise ApocryphaError('error: {v} is not a str or list') from None

        return result

    def append(self, *keys, value):
        ''' string ..., str | list of str -> none | ApocryphaError

        append an element to an apocrypha list. appending to a string creates a
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
            self._query(keys + ['+'] + value)

        except (TypeError, ValueError):
            raise ApocryphaError('error: {v} is not a str or list') from None

    def remove(self, *keys, value):
        ''' string ..., str | list of str -> none | ApocryphaError

        remove an element from a list, if more than one of the element exists
        in the list, only one is removed

        >>> db.set('my', 'list', value=['a', 'b', 'c'])
        >>> db.remove('my', 'list', value='b')
        '''
        keys = list(keys) if keys else ['']

        if isinstance(value, str):
            value = [value]

        if type(value) not in [str, list]:
            raise ApocryphaError('error: {v} is not a str or list') from None

        self._query(keys + ['-'] + value)

    def set(self, *keys, value):
        ''' string ..., string | list | dict | none -> none

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
            self._query(keys + ['--set', value])

        except (TypeError, ValueError):
            raise ApocryphaError(
                'error: value is not JSON serializable') from None

    def apply(self, *keys, func):
        ''' string ..., (list of any -> list of any) -> none

        >>> db.set('colors', value=['blue', 'green', 'red', 'red'])
        >>> db.apply('colors', func=lambda xs: list(set(xs)))
        >>> db.get('colors')
        ['blue', 'green', 'red']
        '''
        keys = list(keys) if keys else ['']

        values = func(self.get(*keys))
        self.set(*keys, value=values)


def network_write(sock, message):
    ''' socket, string -> none
    '''
    try:
        message = struct.pack('>I', len(message)) + message.encode('utf-8')
        sock.sendall(message)

    except (BrokenPipeError, UnicodeDecodeError):
        return False

    else:
        return True


def network_read(sock):
    ''' socket -> string, none
    '''

    def _recv_all(n):
        data = b''

        while len(data) < n:
            fragment = sock.recv(n - len(data))

            if not fragment:
                break
            else:
                data += fragment

        return data

    raw_msg_len = _recv_all(4)
    if not raw_msg_len:
        return None

    msg_len = struct.unpack('>I', raw_msg_len)[0]
    return _recv_all(msg_len).decode('utf-8')


def query(args, host='localhost', port=9999, raw=False, close=True, sock=None):
    ''' list of string -> string | dict | list

    send a query to an Apocrypha server, either returning a list of strings or
    the result of json.loads() on the result '''

    args = list(args)
    remote = (host, port)

    if raw and args and args[-1] not in {'-e', '--edit'}:
        args += ['--edit']

    message = '\n'.join(args) + '\n'

    if not sock:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(remote)

    network_write(sock, message)
    result = network_read(sock)

    if result is None:
        print('something went wrong', args)
        return 'error network length', sock

    if close:
        sock.close()

    result = list(filter(None, result.split('\n')))
    if result and 'error:' in result[0]:
        raise ApocryphaError(result[0]) from None

    if raw:
        result = json.loads(''.join(result)) if result else None

    return result, sock


def _edit_temp_file(temp_file):
    ''' string -> string

    open up the result of the query in a temporary file for manual editing.
    '''
    subprocess.call(['vim', temp_file])

    with open(temp_file, 'r') as fd:
        output = fd.read()

    try:
        output = json.dumps(json.loads(output))

    except ValueError:
        print('error: file has JSON formatting errors')
        time.sleep(1)
        _edit_temp_file(temp_file)

    else:
        return output


def main(args):
    ''' list of string -> IO

    standard query
        ... server

    interactive edit
        ... server --edit

    remote server
        ... -h remote.host.net server '''

    edit_mode = False
    host = 'localhost'

    # check for data in stdin
    if select.select([sys.stdin], [], [], 0.0)[0]:
        args += [sys.stdin.read()]

    # using a non local server
    if args and args[0] in {'-h', '--host'} and args[1]:
        host = args[1]
        args = args[2:]

    # check for edit mode before we make the query
    if args and args[-1] in {'-e', '--edit'}:
        edit_mode = True
        temp_file = '/tmp/apocrypha-' + '-'.join(args[:-1]) + '.json'

    try:
        result = query(args, host=host)
        result = '\n'.join(result)

    except ConnectionRefusedError:
        print('error: could not connect to server')
        sys.exit(1)

    # interactive edit
    if edit_mode:
        with open(temp_file, 'w+') as fd:
            fd.write(result)

        output = _edit_temp_file(temp_file)
        query(args[:-1] + ['--set', output], host=host)

    # result to console
    else:
        print(result)


if __name__ == '__main__':
    main(sys.argv[1:])
