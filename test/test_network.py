#!/usr/bin/env python3

# pylint: disable=protected-access
# pylint: disable=no-self-use
# pylint: disable=missing-docstring
# pylint: disable=too-many-public-methods

import socket
import unittest
import time
import threading
import warnings

from apocrypha.network import write, read

address = ('localhost', 12345)
running = threading.Event()
running.set()


class echo_server():

    def __init__(self):
        self.serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serversocket.bind(address)
        self.serversocket.listen(5)
        self.serversocket.setblocking(0)
        self.connection = None

    def run(self):

        while running.is_set():
            try:
                self.connection, _ = self.serversocket.accept()
                message = self.connection.recv(1024)
                self.connection.send(message)

            except BlockingIOError:
                pass

            finally:
                time.sleep(0.1)

    def stop(self):
        self.serversocket.close()
        if self.connection:
            self.connection.close()


class TestNetwork(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        warnings.simplefilter("ignore", ResourceWarning)
        TestNetwork.server = echo_server()

        TestNetwork.thread = threading.Thread(target=TestNetwork.server.run)
        TestNetwork.thread.start()

    @classmethod
    def tearDownClass(cls):

        running.clear()
        TestNetwork.server.stop()
        TestNetwork.thread.join()

    def setUp(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(address)

    def tearDown(self):
        if self.sock:
            self.sock.close()

    def test_read_write(self):

        msg = 'hello there apple sauce'
        error = write(self.sock, msg)
        self.assertFalse(error)

        result, error = read(self.sock)
        self.assertFalse(error)
        self.assertEqual(msg, result)

    def test_read_write_small(self):

        msg = 'a'
        error = write(self.sock, msg)
        self.assertFalse(error)

        result, error = read(self.sock)
        self.assertFalse(error)
        self.assertEqual(msg, result)

    def test_write_error(self):
        self.sock.close()
        error = write(self.sock, 'hello')
        self.assertTrue(error)

    def test_read_error_general(self):
        self.sock.close()

        _, error = read(self.sock)
        self.assertTrue(error)

    def test_read_error_size(self):
        ''' introduce a failure while reading the body after the message side
        has been received
        '''

        def failure():
            time.sleep(0.001)
            self.sock.close()
        failure_thread = threading.Thread(target=failure)

        msg = 'hello' * 1000
        failure_thread.start()
        write(self.sock, msg)

        result, error = read(self.sock)
        self.assertNotEqual(result, msg)
        self.assertTrue(error)


if __name__ == '__main__':
    unittest.main()
