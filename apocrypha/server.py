#!/usr/bin/env python3

'''
server and handler for database
'''

import os
import socketserver
import time

import apocrypha.client as client
import apocrypha.core

from apocrypha.exceptions import DatabaseError

MILLISECONDS = 10 ** 5


class ServerDatabase(apocrypha.core.Database):
    '''
    wrapper around Database that provides caching
    '''

    def __init__(self, path):
        ''' filepath -> ApocryphaServer

        @path       full path to the database json file
        '''
        apocrypha.core.Database.__init__(self, path)

    def action(self, args):
        ''' list of string -> none

        @args       arguments from the user

        updates self.output with the result of the query

        caching is not allowed for queries that include references or where
        context is requested
        '''

        # all other queries
        cache_key = tuple(args)

        if cache_key in self.cache:
            self.output = self.cache[cache_key]

        else:
            self._action(self.data, args)

            if self.output:
                self.output = '\n'.join(self.output) + '\n'
            else:
                self.output = ''

            self._maybe_cache(args)


class ServerHandler(socketserver.BaseRequestHandler):
    '''
    read query off of the client socket, parse arguments, send response
    '''

    def handle(self):
        ''' none -> none

        self.request is the TCP socket connected to the client
        '''
        client_okay = True

        while client_okay:
            client_okay = self._handle()

    def _handle(self):
        ''' none -> none
        '''
        data = client.network_read(self.request)
        if not data:
            return False

        with self.server.database.lock:
            start_time = _now()
            args = self._parse_arguments(data)
            result = ''

            try:
                self.server.database.action(args)
                result = self.server.database.output

            # user, usage error
            except DatabaseError as error:
                result = str(error)

            # send reply to client
            able_to_reply = client.network_write(self.request, result)
            if not able_to_reply:
                return False

            end_time = _now()
            query_duration = (end_time - start_time) / MILLISECONDS

            # reset internal values, save changes if needed
            self.server.database.post_action()

        self._log(args, query_duration)
        return True

    def _parse_arguments(self, data):
        ''' none -> none

        arguments are delimited by newlines, remove empty elements
        '''

        args = data.split('\n') if data else []
        args = [arg for arg in args if arg]

        while args and args[0] in {'-c', '--context', '-s', '--strict'}:

            if args[0] in {'-c', '--context'}:
                self.server.database.add_context = True

            if args[0] == {'-s', '--strict'}:
                self.server.database.strict = True

            args = args[1:]

        return args

    def _log(self, args, duration):
        ''' list of string -> none
        '''
        if self.server.quiet:
            return

        cache_size = len(self.server.database.cache)
        args = str(args)[:70]

        print('{t:.5f} {c:2} {a}'.format(t=duration, c=cache_size, a=args))


class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    ''' none -> socketserver.TCPServer

    allow address reuse for faster restarts
    '''
    allow_reuse_address = True

    def __init__(self, server_address, handler, database, quiet=False):
        ''' (str, int,), BaseRequestHandler, Database, bool -> Server
        '''
        socketserver.TCPServer.__init__(
            self, server_address, handler)
        self.database = database
        self.quiet = quiet

    def teardown(self):
        ''' none -> none

        stop database writer thread, stop our own threads
        '''
        self.database.writer_running.clear()
        self.shutdown()
        self.server_close()


def _now():
    ''' none -> int
    '''
    return int(round(time.time() * MILLISECONDS))


if __name__ == '__main__':

    # Create the tcp server
    HOST = '0.0.0.0'
    PORT = 9999
    DB_PATH = os.path.expanduser('~') + '/.db.json'

    SERVER = Server(
        (HOST, PORT),
        ServerHandler,
        ServerDatabase(DB_PATH))

    try:
        print('starting')
        SERVER.serve_forever()

    except KeyboardInterrupt:
        print('exiting')

    finally:
        SERVER.teardown()
