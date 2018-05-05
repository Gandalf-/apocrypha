#!/usr/bin/env python3

# pylint: disable=too-many-instance-attributes
# pylint: disable=too-few-public-methods

'''
abstraction of a server that allows communciation with other nodes
'''

import argparse
import os
import queue
import socketserver
import threading
import time
import uuid

import apocrypha.client as client
import apocrypha.database as database
import apocrypha.exceptions as exceptions
import apocrypha.network as network
import apocrypha.server as server


class NodeHandler(socketserver.BaseRequestHandler):
    '''
    read query off of the client socket, send it to the local server, send the
    response back to the client, then maybe forward the query on to peers
    '''

    def handle(self) -> None:
        ''' none -> none

        read in a loop so we can handle multiple requests
        '''
        while True:
            # get the query
            data, error = network.read(self.request)
            if error:
                break
            parsed = [_ for _ in data.split('\n') if _]

            with self.server.lock:
                # check for node to node messages
                parsed, forward = self.server.handle_node_message(parsed)
                if parsed == Node.skip_query:
                    continue

                # get result from local server
                result = self.server.local.query(parsed)
                result = '\n'.join(result) + '\n'

                able_to_reply = network.write(self.request, result)
                if not able_to_reply:
                    break

            # forward query on to peers
            if forward:
                self.server.messages.put(parsed)


class Node(socketserver.ThreadingMixIn, socketserver.TCPServer):
    '''
    a server that forwards requests onto a local database server and
    potentially remote nodes
    '''

    skip_query = 'SKIP_QUERY'
    allow_reuse_address = True

    def __init__(self, node_addr, server_addr, handler, db):
        ''' (str, int), (str, int), BaseRequestHandler, Database -> Node

        create a Node; start our local database server, create a client
        connection to it, save locals, begin checking for peers
        '''
        self.running = threading.Event()
        self.running.set()
        self.lock = threading.Lock()

        # start the local apocrypha server
        self.server = server.Server(
            server_addr,
            server.ServerHandler,
            db,
            quiet=False)

        self.server_thread = threading.Thread(
            target=self.server.serve_forever)
        self.server_thread.start()

        # set locals
        self.node_addr = node_addr          # our host, port
        self.local_port = server_addr[1]    # port of our local server
        self.local = client.Client(         # connection to our local server
            port=self.local_port)
        self.info = self._get_info()

        # start the message forwarding thread
        self.messages = queue.Queue()
        self.forwarder_thread = threading.Thread(
            target=self.forward_to_peers)
        self.forwarder_thread.start()

        # start peer monitoring thread
        self.peers = {}                     # string -> Peer
        self.peers_to_join = self._find_initial_peers()
        self.peer_thread = threading.Thread(target=self.monitor_peers)
        self.peer_thread.start()

        # node server
        socketserver.TCPServer.__init__(
            self,
            ('0.0.0.0', node_addr[1]),
            handler)

    def forward_to_peers(self) -> None:
        ''' list of str -> None

        forward the query onto all of our peers; mark it as a node to node
        message so that it's not fowarded again
        '''
        while self.running.is_set():
            data = self.messages.get()

            for peer in list(self.peers.values()):
                print('forwarding', data, 'to', peer.host, peer.port)
                try:
                    self._recoverable_query(peer, ['--node'] + data)
                except exceptions.FailedQuery:
                    pass

            self.messages.task_done()

    def monitor_peers(self) -> None:
        ''' none -> none

        check peers for more peers to join, connect to all pending peers
        '''
        while self.running.is_set():
            self._check_for_peers()
            self._connect_to_peers()
            time.sleep(5)

    def teardown(self):
        ''' none -> none

        tell our own threads to stop, shutdown the server
        '''
        self.running.clear()
        self.server.teardown()

    def _find_initial_peers(self) -> set:
        ''' none -> set of (str, int,)

        load the peer information we saved from the last time we ran. the
        monitor_peers thread will connect to them
        '''
        peers_to_join = set()
        peers = self.local.get(
            'internal', 'peers', default={})

        for peer in list(peers.values()):
            address = (peer['host'], int(peer['port']),)
            peers_to_join.add(address)

        return peers_to_join

    def _check_for_peers(self) -> None:
        ''' none -> none

        check our peers' peer lists to see if they know anyone we don't,
        also works as a heartbeat to our connected peers
        '''
        for peer in list(self.peers.values()):
            try:
                their_peers = self._recoverable_get(
                    peer, '--node', 'internal', 'peers', '--edit', default={})
            except exceptions.FailedQuery:
                continue

            # remove ourselves from the list
            if self.info['identity'] in their_peers:
                del their_peers[self.info['identity']]

            for their_peer in their_peers:
                if their_peer not in self.peers:
                    host = their_peers[their_peer]['host']
                    port = int(their_peers[their_peer]['port'])
                    self.peers_to_join.add((host, port,))

    def _connect_to_peers(self) -> None:
        ''' none -> none

        try to create Peer objects for each pending peer, if we fail to connect
        we'll try again later
        '''
        print('checking for peers')
        failed_connections = set()
        my_host, my_port = self.node_addr

        for host, port in self.peers_to_join:

            try:
                peer = Peer(host, port)
            except exceptions.PeerCreateFailed:
                failed_connections.add((host, port,))
                continue

            # save their information
            self.peers[peer.identity] = peer
            self.local.set(
                'internal', 'peers', peer.identity,
                value=peer.database_representation())

            # merge
            self._merge(peer)

            # see if they're connected to us
            print('checking their peers...')
            their_peers = peer.client.get(
                '--node', 'internal', 'peers', default={})
            my_identity = self.info['identity']

            # if they're not, tell them to connect to us
            if my_identity not in their_peers:
                try:
                    print('sending connect message', peer.host, peer.port)
                    self._recoverable_query(
                        peer, ['--connect', my_host, str(my_port)])
                except exceptions.FailedQuery:
                    pass
            print('done')

        self.peers_to_join = failed_connections

    def _merge(self, peer) -> None:
        ''' Peer -> none

        see if we should pull the peers data to replace our own
        '''
        our_startup = float(self.local.get('internal', 'local', 'startup'))
        try:
            their_startup = float(
                self._recoverable_get(peer, 'internal', 'local', 'startup'))

            if their_startup < our_startup:
                print('merging with', peer.host, peer.port)

                their_db = self._recoverable_get(peer)
                our_db = self.local.get()

                new_db = their_db
                new_db['internal'] = our_db['internal']
                new_db['internal']['local']['startup'] = str(their_startup)

                self.local.set(value=new_db)

        except exceptions.FailedQuery:
            pass

    def _recoverable_query(self, peer, keys):
        ''' Peer, list of str -> ?

        make a query against the remote peer, if something goes wrong attempt
        to reconnect
        '''
        try:
            return peer.client.query(keys)

        except (ConnectionError, exceptions.DatabaseError) as error:
            print(peer.identity, error)
            self._recover_peer(peer)
            raise exceptions.FailedQuery from None

    def _recoverable_get(self, peer, *keys, default=None, cast=None):
        ''' Peer, any -> ?

        make a get against the remote peer, if something goes wrong attempt
        to reconnect
        '''
        try:
            return peer.client.get(*keys, default=default, cast=cast)

        except (ConnectionError, exceptions.DatabaseError) as error:
            print(peer.identity, error)
            self._recover_peer(peer)
            raise exceptions.FailedQuery from None

    def _get_info(self) -> None:
        ''' none -> none

        update "internal local" to have uuid, host, port. we send this
        information to new peers so they can connect with us
        '''
        data = self.local.get('internal', 'local', default={})

        if 'identity' not in data:
            data['identity'] = str(uuid.uuid4())
        if 'host' not in data:
            data['host'] = self.node_addr[0]
        if 'port' not in data:
            data['port'] = self.node_addr[1]
        data['startup'] = str(time.time())

        self.local.set('internal', 'local', value=data)

        return data

    def _recover_peer(self, peer) -> None:
        ''' Peer -> none

        we hit an error talking to a peer we've successfull connected to
        before, add them back to peers_to_join
        '''
        print('attempting to recover', peer.host, peer.port)

        if peer.identity in self.peers:
            del self.peers[peer.identity]

        self.peers_to_join.add((peer.host, peer.port,))

    def handle_node_message(self, data) -> bool:
        ''' list of string -> bool

        check if the query is a node to node message; this determines if it
        will be forwarded on to our peers
        '''
        # generic forwarded messages from other nodes (or our ourself)
        if data and data[0] == '--node':
            return data[1:], False

        # connect messages from other nodes
        if len(data) == 3 and data[0] == '--connect':
            address = (data[1], int(data[2]),)
            self.peers_to_join.add(address)
            return Node.skip_query, False

        # try to detect read only messages
        if not set(data).intersection(database.WRITE_OPS):
            return data, False

        return data, True


class Peer(object):
    '''
    data encapsulation of a remote peer Node
    '''

    def __init__(self, host, port):
        ''' string, int -> Peer | None

        given a host and port, attempt to connect to another apocrypha node.
        create a client connection with the other node

        if a connection cannot be made, return None
        '''
        print('attempting to connect to', host, port)
        try:
            self.host = host    # str
            self.port = port    # int
            self.client = client.Client(host=host, port=port)
            self.identity = self.client.get(
                '--node', 'internal', 'local', 'identity')
            print('peer connection established with', self.identity)

        except (TimeoutError, ConnectionError):
            print('could not connect to', host, port)
            raise exceptions.PeerCreateFailed

    def database_representation(self):
        '''
        get the database representation of this peer
        '''
        return {
            'identity': self.identity,
            'host': self.host,
            'port': self.port,
        }


def main():
    '''
    create the node, handle teardown
    '''
    if 'AP_CNFG' in os.environ:
        db_path = os.environ['AP_CNFG']
    else:
        db_path = os.path.expanduser('~') + '/.db.json'

    db_host = os.environ['AP_HOST'] if 'AP_HOST' in os.environ else '0.0.0.0'
    db_port = os.environ['AP_PORT'] if 'AP_PORT' in os.environ else 9999
    db_lort = os.environ['AP_LORT'] if 'AP_LORT' in os.environ else 9998

    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str, default=db_host)
    parser.add_argument('--port', type=int, default=db_port)
    parser.add_argument('--localport', type=int, default=db_lort)
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
        node.shutdown()
        node.server_close()


if __name__ == '__main__':
    main()
