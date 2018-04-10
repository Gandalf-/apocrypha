#!/usr/bin/env python3

import argparse
import os
import socketserver
import threading
import uuid

import apocrypha.server as server
import apocrypha.client as client


class NodeHandler(socketserver.BaseRequestHandler):
    '''
    read query off of the client socket, parse arguments, send response
    '''

    def handle(self):
        ''' none -> none

        self.request is the TCP socket connected to the client
        '''
        local = client.Client(port=self.server.local_port)

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

    def __init__(self, node_addr, server_addr, RequestHandlerClass, database):
        ''' (string, int), BaseRequestHandler, Database -> none
        '''

        # node server
        socketserver.TCPServer.__init__(
            self, node_addr, RequestHandlerClass)

        # start the local apocrypha server
        self.server = server.Server(
            server_addr,
            server.ServerHandler,
            database,
            quiet=False)

        self.server_thread = threading.Thread(
                target=self.server.serve_forever)
        self.server_thread.start()

        self.local_port = server_addr[1]
        self.local = client.Client(port=self.local_port)
        self.peers = []

        self.my_info = self._get_my_info()
        self._connect_to_peers()

    def teardown(self):
        ''' none -> none
        '''
        self.server.shutdown()
        self.server.server_close()

        self.server_thread.join(1)

        self.shutdown()
        self.server_close()

    def _connect_to_peers(self):
        ''' none -> none
        '''
        peers_info = self.local.get('internal', 'peers')

        for name, peer in peers_info.items():
            self.peers.append(Peer(name, peer))

    def _get_my_info(self):
        '''
        '''
        local_data = self.local.get('internal', 'local', default={})

        if 'identity' not in local_data:
            local_data['identity'] = str(uuid.uuid4())

        self.local.set('internal', 'local', value=local_data)


class Peer(object):

    def __init__(self, name, info):
        '''
        '''
        print('attempting to connect to', name)
        self.name = name
        self.client = client.Client(
                host=info['host'], port=int(info['port']))

        self.identity = self.client.get('internal', 'local', 'identity')
        print('peer connection established with', self.identity, self.name)


if __name__ == '__main__':
    # Create the tcp server
    host = '0.0.0.0'
    db_path = os.path.expanduser('~') + '/.db.json'

    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=9999)
    parser.add_argument('--localport', type=int, default=9998)
    parser.add_argument('--config', type=str, default=db_path)

    args = parser.parse_args()

    node_address = (host, args.port)
    server_address = ('127.0.0.1', args.localport)

    node = Node(
        node_address,
        server_address,
        NodeHandler,
        server.ServerDatabase(args.config))

    try:
        print('starting')
        node.serve_forever()

    except KeyboardInterrupt:
        print('exiting')

    finally:
        node.teardown()
