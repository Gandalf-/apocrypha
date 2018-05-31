#!/usr/bin/env python3

# pylint: disable=protected-access
# pylint: disable=no-self-use
# pylint: disable=missing-docstring

import unittest

import apocrypha.database
from apocrypha.database import WRITE_OPS, READ_OPS
from apocrypha.exceptions import DatabaseError


testdb = 'test/test-db.json'


def Database(path):
    return apocrypha.database.Database(path, stateless=True)


def run(commands, add_context=False):
    ''' list of list of string -> Apocrypha

    runs the provided commands on a new Apocrypha instance, and then returns
    the instance for inspection
    '''
    a = Database(testdb)
    a.add_context = add_context

    for c in commands:
        a.action(c)

    return a


class TestDatabase(unittest.TestCase):

    def test_basics(self):
        '''
        we can open the database and nothing explodes
        '''
        Database(testdb)

    def test_no_db(self):
        a = Database('file-that-does-not-exist')
        self.assertEqual(a.data, {})

    def test_bad_db(self):
        with self.assertRaises(DatabaseError):
            Database('test/test_core.py')

    def test_index(self):
        '''
        $ d a
        123
        '''
        a = Database(testdb)
        a.action(['a', '=', '123'])
        a.action(['a'])
        self.assertEqual(a.output, ['123'])

    def test_sub_index(self):
        '''
        $ d sub apple
        red
        '''
        a = Database(testdb)
        a.action(['sub', 'apple'])
        self.assertEqual(a.output, ['red'])

    def test_dereference(self):
        '''
        $ d one = two
        $ d two = a b c
        $ d !two
        a b c
        '''
        a = Database(testdb)
        a.action(['!colors'])
        self.assertEqual(a.output, ['nice'])

    def test_context(self):
        a = run([
            ['unique', 'two', 'three', '=', '2'],
            # ['unique', 'three', 'four' '=', '2'],
            ['@', '2'],
        ], add_context=True)

        self.assertEqual(
            a.output,
            ['unique two three = 2'])


class TestDatabaseAssignDelete(unittest.TestCase):

    def test_assign(self):
        '''
        $ d one = two
        $ d one
        two
        '''
        a = Database(testdb)
        a.action(['assign', '=', '123'])
        self.assertEqual(a.data['assign'], '123')

    def test_delete(self):
        '''
        $ d one = two
        $ d one --del
        $ d one
        '''
        a = Database(testdb)
        a.action(['removable', '--del'])
        self.assertFalse('removable' in a.data)

    def test_assign_through_reference(self):
        '''
        $ d one = two three
        $ d !one = four
        $ d two
        four
        $ d three
        four
        '''
        a = Database(testdb)

        args = ['!colors', '=', 'hello']
        a.action(args)

        self.assertEqual(a.data['green'], 'hello')
        self.assertEqual(a.data['blue'], 'hello')
        self.assertEqual(a.data['yellow'], 'hello')

    def test_dereference_list(self):

        a = run([
            ['one', '=', 'two', 'three'],
            ['two', '=', 'hello'],
            ['three', '=', 'there'],
            ['!one'],
        ])

        self.assertEqual(a.output, ['hello', 'there'])

    def test_deep_dereference(self):

        a = run([
            ['one', '=', 'two three'],
            ['two', 'three', '=', 'four'],
            ['!one'],
        ])

        self.assertEqual(a.output, ['four'])

    def test_deep_dereference_list(self):

        a = run([
            ['one', '=', 'two three', 'four five'],
            ['two', 'three', '=', 'apple'],
            ['four', 'five', '=', 'pumpkin'],
            ['!one'],
        ])

        self.assertEqual(a.output, ['apple', 'pumpkin'])

    def test_delete_through_reference(self):

        a = run([
            ['!animals', 'legs', '--del']
        ])

        self.assertEqual(a.data['wolf'], {})
        self.assertEqual(a.data['octopus'], {})
        self.assertEqual(a.data['bird'], {})


class TestDatabaseSymlink(unittest.TestCase):

    def test_symlink(self):

        a = run([
            ['one', '=', '!two'],
            ['two', '=', 'three'],
            ['one']
        ])

        self.assertEqual(a.output, ['three'])

    def test_symlink_list(self):
        a = run([
            ['one', '=', '!two', '!three'],
            ['two', '=', 'apple'],
            ['three', '=', 'pumpkin'],
            ['one']
        ])

        self.assertEqual(a.output, ['apple', 'pumpkin'])

    def test_error_symlink_assign(self):
        '''
        cannot assign through symlinks
        '''
        with self.assertRaises(DatabaseError):
            run([
                ['one', '=', '!two', '!three'],
                ['one', 'four', '=', 'apple'],
            ])

    def test_symlink_list_index(self):
        '''
        index through a list of symlink
        '''
        with self.assertRaises(DatabaseError):
            run([
                ['one', '=', '!two', '!three'],
                ['two', 'sub', '=', 'apple'],
                ['three', 'sub', '=', 'pumpkin'],
                ['one', 'sub']
            ])

    def test_symlink_index(self):
        '''
        index through a symlink
        '''
        a = run([
            ['one', '=', '!two'],
            ['two', 'sub', '=', 'apple'],
            ['one', 'sub']
        ])

        self.assertEqual(a.output, ['apple'])

    def test_symlink_dict(self):
        pass

    def test_symlink_recursion(self):
        a = run([
            ['a', '--del'],
            ['a', 'b', '=', '!b'],
        ])

        self.assertEqual(a.output, [])


class TestDatabaseAppend(unittest.TestCase):

    def test_append_create(self):
        ''' appending to a key that doesn't exist yet
        '''
        a = run([
            ['unique', '+', 'hello'],
            ['unique']
        ])

        self.assertEqual(a.output, ['hello'])
        self.assertTrue(isinstance(a.data['unique'], str))

    def test_append_create_with_space(self):
        ''' appending to a key that doesn't exist yet
        '''
        a = run([
            ['unique', '+', 'hello there'],
            ['unique']
        ])

        self.assertEqual(a.output, ['hello there'])
        self.assertTrue(isinstance(a.data['unique'], str))

    def test_append_to_string(self):
        '''
        appending to a string (singleton value) should convert it to a list
        '''
        a = run([
            ['unique', '=', 'hello there'],
            ['unique', '+', 'apple sauce'],
            ['unique']
        ])

        self.assertEqual(a.output, ['hello there', 'apple sauce'])
        self.assertTrue(isinstance(a.data['unique'], list))

    def test_append_to_list(self):
        a = run([
            ['unique', '=', 'a'],
            ['unique', '+', 'b'],
            ['unique', '+', 'c'],
            ['unique']
        ])

        self.assertEqual(a.output, ['a', 'b', 'c'])
        self.assertTrue(isinstance(a.data['unique'], list))

    def test_append_to_dict(self):
        with self.assertRaises(DatabaseError):
            run([
                ['dict', 'a', '=', '1'],
                ['dict', 'b', '=', '1'],
                ['dict', '+', 'hello']
            ])


class TestDatabaseRemove(unittest.TestCase):

    def test_remove_string(self):
        '''
        list of any -> list to any
        '''
        a = run([
            ['list', '=', 'a', 'b', 'c'],
            ['list', '-', 'a'],
        ])

        self.assertEqual(a.data['list'], ['b', 'c'])

    def test_remove_string_to_string(self):
        a = run([
            ['list', '=', 'a', 'b', 'c'],
            ['list', '-', 'a'],
            ['list', '-', 'b'],
        ])

        self.assertEqual(a.data['list'], 'c')

    def test_remove_from_dict(self):
        with self.assertRaises(DatabaseError):
            run([
                ['list', 'a', '=', 'a', 'b', 'c'],
                ['list', '-', 'a'],
            ])

    def test_remove_from_string(self):
        with self.assertRaises(DatabaseError):
            run([
                ['list', '=', 'c'],
                ['list', '-', 'a'],
            ])

    def test_remove_non_existant(self):
        with self.assertRaises(DatabaseError):
            run([
                ['new list', 'a', '=', 'a', 'b', 'c'],
                ['new list', 'a', '-', 'd'],
            ])

    def test_remove_multi(self):
        a = run([
            ['list', '=', 'a', 'b', 'c'],
            ['list', '-', 'a', 'b'],
        ])

        self.assertEqual(a.data['list'], 'c')


class TestDatabaseKeys(unittest.TestCase):

    def test_keys_on_dict(self):
        '''
        list all the keys under this index
        '''
        a = run([
            ['iron mountain', 'a', '=', '1'],
            ['iron mountain', 'b', '=', '1'],
            ['iron mountain', 'c', '=', '1'],
            ['iron mountain', '--keys']
        ])

        self.assertEqual(
            a.output, ['a', 'b', 'c'])

    def test_keys_on_list(self):
        '''
        error to request keys on a list
        '''
        with self.assertRaises(DatabaseError):
            run([
                ['list', '=', 'a', 'b'],
                ['list', '--keys'],
            ])

    def test_keys_on_value(self):
        '''
        error to request keys on a value
        '''
        with self.assertRaises(DatabaseError):
            run([
                ['value', '=', 'b'],
                ['value', '--keys'],
            ])


class TestDatabaseEdit(unittest.TestCase):
    '''
    d apple --edit

    without an intelligent client, this just dumps the json value of the index
    '''

    def test_edit_list(self):
        a = run([
            ['list', '=', 'a b c d'],
            ['list', '--edit']
        ])

        self.assertEqual(
            a.output, ['"a b c d"'])

    def test_edit_dict(self):
        a = run([
            ['dict', 'a', '=', '1'],
            ['dict', 'b', '=', '2'],
            ['dict', 'c', '=', '3'],
            ['dict', '--edit'],
        ])

        self.assertEqual(
            a.output, ['{\n    "a": "1",\n    "b": "2",\n    "c": "3"\n}'])

    def test_edit_singleton(self):
        a = run([
            ['single', '=', '1'],
            ['single', '--edit'],
        ])

        self.assertEqual(
            a.output, ['"1"'])

    def test_edit_none(self):
        a = run([
            ['unique key', '--edit'],
        ])

        self.assertEqual(
            a.output, ['{}'])


class TestDatabaseSet(unittest.TestCase):
    '''
    d apple --set '["a", "b", "c"]'
    '''

    def test_set_global(self):
        run([
            ['--set', '{"a": 1}'],
            []
        ])

    def test_set_list(self):
        a = run([
            ['list', '=', 'a b c d'],
            ['list', '--set', '["a", "b", "c"]'],
            ['list']
        ])

        self.assertEqual(
            a.output, ['a', 'b', 'c'])

    def test_set_list_of_dict(self):
        a = run([
            ['unique', '--set', '[{"a": "1"}, {"b": "2"}]'],
            ['unique']
        ])

        self.assertEqual(
            a.output, ["{'a': '1'}", "{'b': '2'}"])

    def test_set_dict(self):
        a = run([
            ['dict', '--set', '{"a":"1","b":"2"}'],
            ['dict', 'a'],
            ['dict', 'b']
        ])

        self.assertEqual(
            a.output, ["1", "2"])

    def test_set_singleton(self):
        a = run([
            ['single', '--set', '"hello"'],
            ['single']
        ])

        self.assertEqual(
            a.output, ['hello'])

    def test_set_json_error(self):
        a = Database(testdb)

        args = ['broken', '--set', 'gobbeldy gook']

        with self.assertRaises(DatabaseError):
            a.action(args)


class TestDatabaseSearch(unittest.TestCase):

    def test_search_list(self):
        a = run([
            ['list', '=', 'haystack', 'haystack', 'needle'],
            ['other', '=', 'haystack', 'haystack'],
            ['@', 'needle'],
        ])

        self.assertEqual(
            a.output, ['list = needle'])

    def test_search_dict(self):
        a = run([
            ['blue', 'berry', '=', 'octopus'],
            ['blue', 'cobbler', '=', 'squid'],
            ['@', 'squid'],
        ])

        self.assertEqual(
            a.output, ['blue cobbler = squid'])

    def test_error_search_singleton(self):
        a = run([
            ['value', '=', 'needle'],
            ['@', 'needle'],
        ])

        self.assertEqual(
            a.output, ['value = needle'])


class TestDatabaseErrors(unittest.TestCase):

    def test_list_subtract_error(self):
        a = Database(testdb)

        args = ['list', '-', 'applesauce']

        with self.assertRaises(DatabaseError):
            a.action(args)

    def test_list_subtract_non_list(self):
        a = Database(testdb)

        args = ['green', '-', 'applesauce']

        with self.assertRaises(DatabaseError):
            a.action(args)

    def test_index_into_value(self):

        with self.assertRaises(DatabaseError):
            run([
                ['green', 'nice', 'failure']
            ])


class TestCache(unittest.TestCase):

    def test_add(self):
        a = Database(testdb)

        a.output = 'value'
        a._maybe_cache(['key'])

        self.assertEqual(
            a.cache, {('key',): 'value'})

    def test_add_deep(self):
        a = Database(testdb)

        a.output = 'value'
        a._maybe_cache(['apple', 'blue', 'berry'])

        self.assertEqual(
            a.cache, {('apple', 'blue', 'berry'): 'value'})

    def test_add_read_op(self):
        a = Database(testdb)

        a.output = 'value'
        a._maybe_cache(['key'])

        for op in READ_OPS:
            a._maybe_cache(['apple', op])

        output = {
            ('apple', '-e'): 'value', ('apple', '--keys'): 'value',
            ('apple', '-k'): 'value', ('apple', '--edit'): 'value',
            ('key',): 'value'}

        self.assertEqual(a.cache, output)

    def test_write_op_not_added(self):
        a = Database(testdb)

        for op in WRITE_OPS:
            a._maybe_cache(['apple', op, 'value'])
            self.assertEqual(a.cache, {})


if __name__ == '__main__':
    unittest.main()
