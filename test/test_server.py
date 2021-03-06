#!/usr/bin/env python3

# pylint: disable=protected-access
# pylint: disable=no-self-use
# pylint: disable=missing-docstring
# pylint: disable=too-many-public-methods

import time
import threading
import unittest

import apocrypha.client
from apocrypha.exceptions import DatabaseError
from apocrypha.server import ServerDatabase, ServerHandler, Server
from test_node import random_query

PORT = 49999

client = apocrypha.client.Client(port=PORT)


def query(args, raw=False):
    ''' list of string -> string
    '''
    return client.query(args, interpret=raw)


class TestServerBase(unittest.TestCase):

    database = None
    server = None
    server_thread = None

    @classmethod
    def setUpClass(cls):
        '''
        create an Apocrypha instance and server to handle connections
        run the server in a thread so test cases may run
        '''
        # create the ServerDatabase instance, which inherits from Apocrypha
        TestServerBase.database = ServerDatabase(
            'test/test-db.json',
            stateless=True)

        # Create the tcp server
        host, port = '0.0.0.0', PORT
        TestServerBase.server = Server(
            (host, port), ServerHandler,
            TestServerBase.database, quiet=True)

        # start the server
        TestServerBase.server_thread = threading.Thread(
            target=TestServerBase.server.serve_forever)

        TestServerBase.server_thread.start()
        TestServerBase.db = apocrypha.client.Client(port=PORT)

    @classmethod
    def tearDownClass(cls):
        '''
        shutdown the server
        '''
        TestServerBase.server.teardown()
        TestServerBase.server.socket.close()
        TestServerBase.server_thread.join(1)

class TestServer(TestServerBase):

    # server tests
    #   caching
    def test_cache_hit(self):

        # write operations don't update the cache
        query(['pizza', '=', 'sauce'])
        self.assertNotIn(('pizza',), TestServer.database.cache)

        # get operations do
        query(['pizza'])

        self.assertIn(('pizza',), TestServer.database.cache)
        result = query(['pizza'])

        self.assertEqual(result, ['sauce'])
        self.assertIn(('pizza',), TestServer.database.cache)

    def test_cache_deep_hit(self):
        query(['a', '-d'])
        query(['a', 'b', 'c', 'd', 'e', '=', 'f'])
        query(['a', 'b', 'c', 'd', 'e'])

        self.assertIn(
            ('a', 'b', 'c', 'd', 'e'),
            TestServer.database.cache)

    @unittest.skip('using simple caching')
    def test_cache_invalidate(self):
        query(['pizza', '=', 'sauce'])

        query(['pizza'])
        query([])
        self.assertIn(('pizza',), TestServer.database.cache)
        self.assertIn((), TestServer.database.cache)

        query(['pizza', '-d'])
        self.assertNotIn(('pizza',), TestServer.database.cache)
        self.assertNotIn((), TestServer.database.cache)

    @unittest.skip('using simple caching')
    def test_cache_invalidate_parent(self):
        '''
        changing a child key invalidates all of it's parents
        '''
        query(['one layer', 'two layer', '=', 'cake'])

        query(['one layer', 'two layer'])
        self.assertIn(('one layer', 'two layer'), TestServer.database.cache)

        query(['one layer'])
        self.assertIn(('one layer',), TestServer.database.cache)

        # both parent and child are in cache, now change the child and make
        # sure the parent is also invalidated

        query(['one layer', 'two layer', '=', 'goop'])

        self.assertNotIn(('one layer', 'two layer'), TestServer.database.cache)
        self.assertNotIn(('one layer',), TestServer.database.cache)

    @unittest.skip('using simple caching')
    def test_cache_invalidate_child(self):
        '''
        changing a parent key invalidates all of it's direct children
        '''
        query(['one layer', 'two layer', '=', 'cake'])

        query(['one layer', 'two layer'])
        self.assertIn(('one layer', 'two layer'), TestServer.database.cache)

        query(['one layer'])
        self.assertIn(('one layer',), TestServer.database.cache)

        # both parent and child are in cache, now change the parent and make
        # sure the child is also invalidated

        query(['one layer', '-d'])

        self.assertNotIn(('one layer', 'two layer'), TestServer.database.cache)
        self.assertNotIn(('one layer',), TestServer.database.cache)

    @unittest.skip('unknown issue')
    def test_cache_doesnt_effect_sibling(self):
        client.delete('one layer')

        client.set('one layer', 'two layer', value='cake')
        client.set('one layer', 'apple layer', value='sauce')
        print(TestServer.database.data)

        self.assertEqual(
            client.get('one layer', 'two layer'), 'cake')
        self.assertEqual(
            client.get('one layer', 'apple layer'), 'sauce')
        self.assertEqual(
            client.get('one layer'),
            {'two layer': 'cake', 'apple layer': 'sauce'})

        print(TestServer.database.cache)
        self.assertIn(('one layer',), TestServer.database.cache)
        self.assertIn(('one layer', 'two layer',), TestServer.database.cache)
        self.assertIn(('one layer', 'apple layer',), TestServer.database.cache)

    def test_cache_top_level_read_operators(self):
        '''
        make sure --keys, --edit on root are invalidated correctly
        '''
        pass

    def test_cache_top_level_write_operators(self):
        '''
        writing to root clears the entire cache
        '''
        pass

    def test_cache_write_ops_not_cached(self):
        pass

    def test_cache_read_ops_are_cached(self):
        query(['pizza', '=', 'sauce'])
        value = query(['pizza', '--edit'])

        self.assertIn(('pizza', '--edit',), TestServer.database.cache)
        self.assertEqual(value, ['"sauce"'])

    #  timing
    @unittest.skip('timing not currently supported')
    def test_timing(self):
        result = query(['-t', 'wolf', 'legs'])
        self.assertEqual(result, ['0'])

        query(['wolf', 'legs', '=', '4'])

        result = query(['-t', 'wolf', 'legs'])
        self.assertNotEqual(result, ['0'])

    # client tests - query
    def test_assign(self):
        query(['apple', '=', 'sauce'])
        result = query(['apple'])

        self.assertEqual(result, ['sauce'])

    def test_strict(self):
        with self.assertRaises(DatabaseError):
            query(['-s', 'gadzooks'])

    def test_context(self):
        result = query(['-c', '@', 'red'])
        self.assertEqual(result, ['sub apple = red'])

    def test_query_json_dict(self):
        result = query(['octopus'], raw=True)
        self.assertEqual(result, {'legs': 8})
        self.assertTrue(isinstance(result, dict))

    def test_query_json_list(self):
        result = query(['colors'], raw=True)
        self.assertTrue(isinstance(result, list))

    def test_query_json_string(self):
        result = query(['apple'], raw=True)
        self.assertTrue(isinstance(result, str))

    # client tests - Client
    def test_get_string(self):
        self.assertEqual(
            TestServer.db.get('green'), 'nice')

        self.assertEqual(
            TestServer.db.get('octopus', 'legs'), 8)

    # get
    def test_get_list(self):
        self.assertEqual(
            TestServer.db.get('animals'),
            ['wolf', 'octopus', 'bird'])

    def test_get_dict(self):
        self.assertEqual(
            TestServer.db.get('octopus'),
            {'legs': 8})

    def test_get_non_existant(self):
        self.assertEqual(
            TestServer.db.get('yahoo', 'foobar'),
            None)

    def test_get_default(self):
        '''
        when a key doesn't exist, default=<something> determines what to
        respond with
        '''
        self.assertEqual(
            TestServer.db.get('yahoo', 'foobar', default={}),
            {})

        self.assertEqual(
            TestServer.db.get('yahoo', 'foobar', default=[]),
            [])

        self.assertEqual(
            TestServer.db.get('yahoo', 'foobar', default='abc'),
            'abc')

    def test_get_error(self):
        with self.assertRaises(DatabaseError):
            TestServer.db.get('animals', 'octopus')

    def test_get_cast_to_list(self):
        self.assertEqual(
            TestServer.db.get('green', cast=list),
            ['nice'])

    def test_get_cast_to_str(self):
        self.assertEqual(
            TestServer.db.get('animals', cast=str),
            "['wolf', 'octopus', 'bird']")

    def test_get_cast_to_set(self):
        self.assertEqual(
            TestServer.db.get('animals', cast=set),
            {'wolf', 'octopus', 'bird'})

    def test_get_cast_to_error(self):
        with self.assertRaises(DatabaseError):
            TestServer.db.get('animals', cast=dict)

    # keys
    def test_keys(self):
        self.assertEqual(
            TestServer.db.keys('octopus'), ['legs'])

    def test_keys_non_existant(self):
        self.assertEqual(
            TestServer.db.keys('does not exist', 'foobar'), [])

    def test_keys_error(self):
        with self.assertRaises(DatabaseError):
            TestServer.db.keys('animals', 'octopus')

    # remove
    def test_remove(self):
        TestServer.db.set('test list', value=['a', 'b', 'c'])
        TestServer.db.remove('test list', value='a')
        self.assertEqual(
            TestServer.db.get('test list'),
            ['b', 'c'])

    def test_remove_list(self):
        TestServer.db.set('test list', value=['a', 'b', 'c'])
        TestServer.db.remove('test list', value=['a', 'b'])
        self.assertEqual(
            TestServer.db.get('test list'),
            'c')

    def test_remove_error(self):
        with self.assertRaises(DatabaseError):
            TestServer.db.remove('octopus', value='sandwich')

    def test_remove_type_error(self):
        TestServer.db.set('octopus', value={1: 2, 3: 4})

        with self.assertRaises(DatabaseError):
            TestServer.db.remove('octopus', value='sandwich')

    def test_remove_error_top_level(self):
        with self.assertRaises(DatabaseError):
            TestServer.db.remove(value='key that does not exist')

    # append
    def test_append(self):
        TestServer.db.delete('test list')

        TestServer.db.append('test list', value='apple')
        self.assertEqual(
            TestServer.db.get('test list'),
            'apple')

        TestServer.db.append('test list', value='blue')
        self.assertEqual(
            TestServer.db.get('test list'),
            ['apple', 'blue'])

    def test_append_list(self):
        TestServer.db.delete('test list')

        TestServer.db.append('test list', value=['a', 'b'])
        self.assertEqual(
            TestServer.db.get('test list'),
            ['a', 'b'])

        TestServer.db.append('test list', value=['c', 'd'])
        self.assertEqual(
            TestServer.db.get('test list'),
            ['a', 'b', 'c', 'd'])

    def test_append_non_existant(self):
        TestServer.db.delete('test list')

        TestServer.db.append('test list', value=['a', 'b'])
        self.assertEqual(
            TestServer.db.get('test list'),
            ['a', 'b'])

    def test_append_error(self):
        with self.assertRaises(DatabaseError):
            TestServer.db.append('octopus', value='sandwich')

    def test_append_type_error(self):
        with self.assertRaises(DatabaseError):
            TestServer.db.append('octopus', value={'a': 1})

    # set
    def test_set(self):

        TestServer.db.set('test item', value='hello')
        value = TestServer.db.get('test item')
        self.assertEqual(value, 'hello')

    def test_set_list(self):
        TestServer.db.set('test list', value=['hello', 'there'])
        self.assertEqual(
            TestServer.db.get('test list'),
            ['hello', 'there'])

    def test_set_error(self):
        with self.assertRaises(DatabaseError):
            TestServer.db.set('hello', value=set())

    # delete
    def test_delete(self):
        TestServer.db.set('test item', value='hello')
        self.assertEqual(
            TestServer.db.get('test item'),
            'hello')
        TestServer.db.delete('test item')
        self.assertEqual(
            TestServer.db.get('test item'),
            None)

    # pop
    def test_pop_cast(self):
        TestServer.db.set('item', value='hello')

        result = TestServer.db.pop('item', cast=list)
        self.assertEqual(
            result, list('hello'))

    def test_pop_bad_cast(self):
        TestServer.db.set('item', value='hello')

        with self.assertRaises(DatabaseError):
            TestServer.db.pop('item', cast=dict)

    # apply
    def test_apply(self):
        TestServer.db.set('list', value=['a', 'a', 'b', 'c'])
        TestServer.db.apply('list', func=lambda xs: list(set(xs)))
        self.assertEqual(
            sorted(TestServer.db.get('list')),
            sorted(['a', 'b', 'c']))

    # raw query
    def test_query(self):
        self.assertEqual(
            apocrypha.client.query(
                ['non', 'existant', '--keys'], port=PORT),
            [])

    def test_fuzz(self):
        ''' throw a ton of junk at the server and see if it crashes
        '''
        for _ in range(0, 1000):
            random_query(client, debug=False)

    def test_lock_stress(self):
        ''' make a ton of junk queries from several threads

        not interested in what the queries do, just that they don't crash the
        server
        '''
        num_requests = 500
        num_workers = 10

        def worker():
            time.sleep(0.1)
            for _ in range(0, num_requests):
                random_query(client, debug=False)

        threads = []
        for _ in range(0, num_workers):
            threads += [
                threading.Thread(target=worker)
            ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()


if __name__ == '__main__':
    unittest.main()
