#!/usr/bin/env python3

import os
import socketserver
import threading

from apocrypha.server import Server, ApocryphaHandler, ApocryphaServer
import apocrypha.client as client


class NodeHandler(socketserver.BaseRequestHandler):
    '''
    read query off of the client socket, parse arguments, send response
    '''

    def handle(self):
        ''' none -> none

        self.request is the TCP socket connected to the client
        '''
        local = client.Client(port=9998)

        while True:
            data = client.network_read(self.request)
            if not data:
                break
            data = [_ for _ in data.split('\n') if _]
            print('node got a message')

            result = local.query(data)
            result = '\n'.join(result) + '\n'

            able_to_reply = client.network_write(self.request, result)
            if not able_to_reply:
                break


class Node(socketserver.ThreadingMixIn, socketserver.TCPServer):

    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, database):
        ''' (string, int), BaseRequestHandler, Database -> none
        '''

        # node server
        socketserver.TCPServer.__init__(
            self, server_address, RequestHandlerClass)

        # start the local apocrypha server
        self.server = Server(
            ('127.0.0.1', 9998),
            ApocryphaHandler,
            database,
            quiet=False)

        self.server_thread = threading.Thread(
                target=self.server.serve_forever)
        self.server_thread.start()
        self.management_local = client.Client(port=9998)

    def _connect_to_peers(self):
        ''' none -> none
        '''

    def teardown(self):
        ''' none -> none
        '''
        self.server.shutdown()
        self.server.server_close()

        self.server_thread.join(1)

        self.shutdown()
        self.server_close()


if __name__ == '__main__':
    # Create the tcp server
    host = '0.0.0.0'
    port = 9999
    db_path = os.path.expanduser('~') + '/.db.json'

    node = Node(
        (host, port),
        NodeHandler,
        ApocryphaServer(db_path))

    try:
        print('starting')
        node.serve_forever()

    except KeyboardInterrupt:
        print('exiting')

    finally:
        node.teardown()
