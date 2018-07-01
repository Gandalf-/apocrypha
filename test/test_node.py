#!/usr/bin/env python3

# pylint: disable=protected-access
# pylint: disable=no-self-use
# pylint: disable=missing-docstring
# pylint: disable=too-many-public-methods

import random
import time
import threading
import unittest
import warnings

import apocrypha.client
from apocrypha.server import ServerDatabase
from apocrypha.node import NodeHandler, Node

alpha_port = 4999
beta_port = 5999
omega_port = 6999

alpha_client = apocrypha.client.Client(port=alpha_port)
beta_client = apocrypha.client.Client(port=beta_port)
omega_client = apocrypha.client.Client(port=omega_port)


def random_query(client):

    options = [client.set, client.append, client.pop, client.delete]
    targets = ['one', 'two', 'three', 'four', 'five']

    choice = random.choice(options)
    target = random.choice(targets)
    value = str(random.randint(0, 10000))

    if choice in [client.pop, client.delete]:
        choice(target)
    else:
        choice(target, value=value)


def grab_all(client):
    ''' retreive everything except for 'internal' key
    '''
    result = client.get()
    del result['internal']
    return result


def verify_peers(client, ports):
    ''' list of int -> bool
    '''
    result = client.get('internal', 'peers')

    result_ports = [result[peer]['port'] for peer in result]
    return sorted(result_ports) == sorted(ports)


def make_node(external_port):
    internal_port = external_port - 1

    node_address = ('localhost', external_port)
    server_address = ('localhost', internal_port)

    database = ServerDatabase(
        'test/test-db.json',
        stateless=True)

    node = Node(
        node_address,
        server_address,
        NodeHandler,
        database,
        quiet=False)

    # start the alpha node
    node_thread = threading.Thread(
        target=node.serve_forever)

    node_thread.start()

    return node, node_thread


def ignore_warnings(test_func):
    def do_test(self, *args, **kwargs):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            test_func(self, *args, **kwargs)
    return do_test


class TestNode(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        '''
        create an Apocrypha instance and server to handle connections
        run the server in a thread so test cases may run
        '''
        TestNode.alpha_node, TestNode.alpha_node_thread = \
            make_node(alpha_port)

        TestNode.beta_node, TestNode.beta_node_thread = \
            make_node(beta_port)

        TestNode.omega_node, TestNode.omega_node_thread = \
            make_node(omega_port)

        # give the nodes time to get set up
        time.sleep(5)

    @classmethod
    def tearDownClass(cls):
        '''
        shutdown the server
        '''
        warnings.simplefilter("ignore", ResourceWarning)

        print('\ntearing down, may take up to 5 seconds')
        alpha_client.sock.close()
        beta_client.sock.close()
        omega_client.sock.close()

        TestNode.alpha_node.teardown()
        TestNode.beta_node.teardown()
        TestNode.omega_node.teardown()

        TestNode.alpha_node_thread.join(1)
        TestNode.beta_node_thread.join(1)
        TestNode.omega_node_thread.join(1)

    def test_1_alpha_sanity(self):
        alpha_client.set('apple', value='sauce')
        result = alpha_client.get('apple')
        self.assertEqual(result, 'sauce')

    def test_2_beta_sanity(self):
        beta_client.set('apple', value='sauce')
        result = beta_client.get('apple')
        self.assertEqual(result, 'sauce')

    def test_3_omega_sanity(self):
        omega_client.set('apple', value='sauce')
        result = omega_client.get('apple')
        self.assertEqual(result, 'sauce')

    @ignore_warnings
    def test_4_connect(self):
        ''' alpha --connect -> beta

        have alpha send a connect message to beta. beta will respond and merge
        with alpha

        we should see beta's information in alpha's peer dict, and vice versa
        '''
        # send the connect query
        alpha_client.query(['--connect', 'localhost', str(beta_port)])

        # give alpha time to react and update it's peer information with beta's
        # information
        time.sleep(5)

        result = alpha_client.get('internal', 'peers')
        self.assertTrue(verify_peers(alpha_client, [beta_port]))

        # give beta time to connect back to alpha
        time.sleep(5)

        result = beta_client.get('internal', 'peers')
        alpha = list(result.keys())[0]

        peer_port = result[alpha]['port']
        self.assertEqual(peer_port, alpha_port)

    @ignore_warnings
    def test_5_connect_omega(self):
        ''' alpha --connect omega

        by this time, alpha and beta are already joined. connecting alpha to
        omega should connect omega to alpha, then beta will notice omega in
        alpha's peer list and connect to them. finally, omega will connect to
        beta to complete the mesh
        '''
        # send the alpha -> omega connect query
        alpha_client.query(['--connect', 'localhost', str(omega_port)])

        # give alpha time to react and update it's peer information with
        # omega's information
        time.sleep(5)

        # make sure that beta and omega are in alpha's peers
        self.assertTrue(
            verify_peers(alpha_client, [beta_port, omega_port]))

        # give omega time to connect back to alpha, and beta
        # beta time to connect to omega
        time.sleep(5)
        self.assertTrue(
            verify_peers(omega_client, [beta_port, alpha_port]))

        self.assertTrue(
            verify_peers(beta_client, [alpha_port, omega_port]))

    def test_5_write_query(self):
        ''' send a write query to alpha, make sure everyone in the mesh
        receives it
        '''
        alpha_client.set('blue', value='berry')
        a = alpha_client.get('blue')

        time.sleep(2)
        b = beta_client.get('blue')
        o = omega_client.get('blue')

        self.assertTrue(a == 'berry', a)
        self.assertTrue(b == 'berry', b)
        self.assertTrue(o == 'berry', o)

    def test_6_sychronize_one_direction(self):
        ''' send a bunch of messages to one node, make sure everyone is
        eventually consistent '''

        for _ in range(0, 100):
            random_query(alpha_client)

        # give nodes time to synchronize
        time.sleep(5)

        a = grab_all(alpha_client)
        b = grab_all(beta_client)
        o = grab_all(omega_client)

        self.assertEqual(a, b)
        self.assertEqual(b, o)
        self.assertEqual(a, o)

    @unittest.skip('not implemented')
    def test_7_sychronize_two_directions(self):
        ''' send a bunch of messages to two nodes, make sure everyone is
        eventually consistent '''

        self.maxDiff = None

        for _ in range(0, 50):
            random_query(alpha_client)
            random_query(beta_client)

        # give nodes time to synchronize
        time.sleep(10)

        a = grab_all(alpha_client)
        b = grab_all(beta_client)
        o = grab_all(omega_client)

        self.assertEqual(a, b)
        self.assertEqual(b, o)
        self.assertEqual(a, o)


if __name__ == '__main__':
    unittest.main()
