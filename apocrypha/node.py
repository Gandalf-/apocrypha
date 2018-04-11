#!/usr/bin/env python3

import argparse
import os
import socketserver
import threading
import time
import uuid

import apocrypha.server as server
import apocrypha.client as client


class PeerConnectionFailed(Exception):
    pass


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

            # get the query
            data = client.network_read(self.request)
            if not data:
                break
            parsed = [_ for _ in data.split('\n') if _]

            # check for node to node messages
            forward = True
            if self.server.is_node_message(parsed):
                parsed = parsed[1:]
                forward = False

            # get result from local server
            result = local.query(parsed)
            result = '\n'.join(result) + '\n'

            able_to_reply = client.network_write(self.request, result)
            if not able_to_reply:
                break

            # forward query on to peers
            if forward:
                self.server.forward_to_peers(parsed)


class Node(socketserver.ThreadingMixIn, socketserver.TCPServer):

    allow_reuse_address = True

    def __init__(self, node_addr, server_addr, RequestHandlerClass, database):
        ''' (str, int), (str, int), BaseRequestHandler, Database -> Node

        create a Node; start our local database server, create a client
        connection to it, save locals, begin checking for peers
        '''
        self.running = threading.Event()
        self.running.set()

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

        # set locals
        self.node_addr = node_addr          # our host, port
        self.local_port = server_addr[1]    # port of our local server
        self.local = client.Client(         # connection to our local server
                port=self.local_port)
        self.peers = {}                     # string -> Peer
        self.info = self._get_info()

        # start peer monitoring thread
        self.peer_thread = threading.Thread(
                target=self._connect_to_peers)
        self.peer_thread.start()

    def is_node_message(self, data):
        ''' list of string -> bool

        check if the query is a node to node message; this determines if it
        will be forwarded on to our peers
        '''
        if data and '--node' == data[0]:
            print('node taking', data, 'not fowarding')
            return True

        return False

    def forward_to_peers(self, data):
        ''' list of str -> None

        forward the query onto all of our peers; mark it as a node to node
        message so that it's not fowarded again
        '''

        for peer in self.peers.values():
            print('forwarding', data, 'to', peer.name)
            peer.client.query(['--node'] + data)

    def teardown(self):
        ''' none -> none
        '''
        self.running.clear()
        self.server.shutdown()
        self.server.server_close()

        self.server_thread.join(1)

        self.shutdown()
        self.server_close()

    def _connect_to_peers(self):
        ''' none -> none
        '''
        while self.running.is_set():
            peers_info = self.local.get(
                    'internal', 'peers', default={})

            for name, peer_info in peers_info.items():

                # don't attempt to reconnect to peers
                if name in self.peers:
                    continue

                try:
                    new = Peer(name, peer_info)

                except PeerConnectionFailed:
                    continue

                # save their information
                self.peers[name] = new
                self.local.set(
                        'internal', 'peers', name, 'identity',
                        value=new.identity)

                # see if they're connected to us
                their_peers = new.client.get(
                        '--node', 'internal', 'peers', default={})
                my_identity = self.info['identity']
                match = False

                for their_peer in their_peers.values():
                    if their_peer['identity'] == my_identity:
                        match = True

                # if they're not, add ourselves to their peer list
                if not match:
                    my_name = self.info['identity']
                    new.client.set(
                            '--node', 'internal', 'peers', my_name,
                            value=self.info)

            time.sleep(5)

    def _get_info(self):
        '''
        update "internal local" to have uuid, host, port. we send this
        information to new peers so they can connect with us
        '''
        local_data = self.local.get('internal', 'local', default={})

        if 'identity' not in local_data:
            local_data['identity'] = str(uuid.uuid4())

        local_data['host'] = self.node_addr[0]
        local_data['port'] = self.node_addr[1]

        self.local.set('internal', 'local', value=local_data)

        return local_data


class Peer(object):

    def __init__(self, name, info):
        ''' string, { 'host': str, 'port': int } -> Peer | None

        given a host and port, attempt to connect to another apocrypha node.
        create a client connection with the other node

        if a connection cannot be made, return None
        '''
        print('attempting to connect to', name)
        try:
            self.name = name
            self.client = client.Client(
                    host=info['host'], port=int(info['port']))

            self.identity = self.client.get(
                    '--node', 'internal', 'local', 'identity')

            print('peer connection established with', self.identity, self.name)

        except ConnectionRefusedError:
            print('could not connect to', name)
            raise PeerConnectionFailed


if __name__ == '__main__':
    # Create the tcp server
    db_path = os.path.expanduser('~') + '/.db.json'

    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str, default='127.0.0.1')
    parser.add_argument('--port', type=int, default=9999)
    parser.add_argument('--localport', type=int, default=9998)
    parser.add_argument('--config', type=str, default=db_path)

    args = parser.parse_args()

    node_address = (args.host, args.port)
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
