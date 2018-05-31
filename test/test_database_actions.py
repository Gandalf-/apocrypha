#!/usr/bin/env python3

'''
database action unit tests
'''

# pylint: disable=protected-access
# pylint: disable=no-self-use
# pylint: disable=missing-docstring

import unittest
import apocrypha.database
from apocrypha.exceptions import DatabaseError

CFG = '/tmp/db.json'
DB = apocrypha.database.Database(CFG, stateless=True)


class TestSearch(unittest.TestCase):
    ''' search '''

    def setUp(self):
        DB.post_action()


class TestAppend(unittest.TestCase):
    ''' append '''

    def setUp(self):
        DB.post_action()

    def test_create_new_value_single(self):
        ''' single to single '''
        base = {'a': {}}
        left = 'a'
        right = ['b']
        DB._append(base, left, right)

        self.assertEqual(base[left], 'b')

    def test_create_new_value_list(self):
        ''' list to list '''
        base = {'a': {}}
        left = 'a'
        right = ['a', 'b']
        DB._append(base, left, right)

        self.assertEqual(base[left], right)

    def test_create_new_value_list_one_elem(self):
        ''' lists of a single element are converted to singletons '''
        base = {'a': {}}
        left = 'a'
        right = ['a']
        DB._append(base, left, right)

        self.assertEqual(base[left], 'a')

    def test_error_append_to_dict(self):
        ''' cannot append to a dict '''
        base = {'a': {'1': '2'}}
        left = 'a'
        right = ['a']

        with self.assertRaises(DatabaseError):
            DB._append(base, left, right)

    def test_append_to_singleton_makes_list(self):
        ''' single to list
        '''
        base = {'a': '1'}
        left = 'a'
        right = ['b']

        DB._append(base, left, right)
        self.assertEqual(base[left], ['1', 'b'])

    def test_append_to_list_is_list(self):
        ''' list to list
        '''
        base = {'a': ['1', '2']}
        left = 'a'
        right = ['b']

        DB._append(base, left, right)
        self.assertEqual(base[left], ['1', '2', 'b'])

    def test_append_list_to_list(self):
        ''' list to list
        '''
        base = {'a': ['1', '2']}
        left = 'a'
        right = ['b', 'c']

        DB._append(base, left, right)
        self.assertEqual(base[left], ['1', '2', 'b', 'c'])


class TestAssign(unittest.TestCase):
    ''' assign '''

    def setUp(self):
        DB.post_action()

    def test_single(self):
        ''' basic assignment '''
        base = {'a': {}}
        left = 'a'
        right = ['b']

        DB._assign(base, left, right)
        self.assertEqual(base[left], 'b')

    def test_list(self):
        ''' list assign '''
        base = {'a': {}}
        left = 'a'
        right = ['b', 'c']

        DB._assign(base, left, right)
        self.assertEqual(base[left], right)

    def test_no_write_if_equal(self):
        base = {'a': '1'}
        left = 'a'
        right = ['1']

        DB._assign(base, left, right)
        self.assertEqual(base[left], '1')
        self.assertFalse(DB.write_needed)


class TestKeys(unittest.TestCase):
    ''' keys '''

    def setUp(self):
        DB.post_action()

    def test_no_keys(self):
        base = {}
        left = 'a'

        DB._keys(base, left)
        self.assertEqual(DB.output, [])

    def test_one_key(self):
        base = {'a': 1}
        left = 'a'

        DB._keys(base, left)
        self.assertEqual(DB.output, ['a'])

    def test_multiple_keys(self):
        base = {'a': 1, 'b': 2}
        left = 'a'

        DB._keys(base, left)
        self.assertEqual(DB.output, ['a', 'b'])

    def test_error_keys_on_non_dict(self):
        ''' cannot get keys on a non dict '''
        base = []
        left = 'a'

        with self.assertRaises(DatabaseError):
            DB._keys(base, left)

        base = '1'
        with self.assertRaises(DatabaseError):
            DB._keys(base, left)


class TestSet(unittest.TestCase):
    ''' set '''

    def setUp(self):
        DB.post_action()

    def test_simple(self):
        base = {'a': 1}
        left = 'a'
        right = '"apple"'

        DB._set(base, left, right)
        self.assertEqual(base[left], "apple")

    def test_global_overwrite(self):
        base = {}
        left = ''
        right = '{"a": 1}'

        DB._set(base, left, right)
        self.assertEqual(DB.data, {'a': 1})
        DB.data = {}

    def test_error_global_overwrite_non_dict(self):
        base = {}
        left = ''
        right = '"apple"'

        with self.assertRaises(DatabaseError):
            DB._set(base, left, right)
        self.assertFalse(DB.write_needed)

    def test_no_write_if_equal(self):
        base = {'a': 1}
        left = 'a'
        right = '1'

        DB._set(base, left, right)
        self.assertEqual(base[left], 1)
        self.assertFalse(DB.write_needed)

    def test_error_not_json(self):
        base = {'a': 1}
        left = 'a'
        right = '{apple'

        with self.assertRaises(DatabaseError):
            DB._set(base, left, right)
        self.assertFalse(DB.write_needed)


class TestRemove(unittest.TestCase):
    ''' remove one or more elements from anything '''

    def setUp(self):
        DB.post_action()

    def test_one_from_single(self):
        base = {'a': 1}
        left = 'a'
        right = [1]

        DB._remove(base, left, right)
        self.assertTrue(left not in base)

    def test_one_from_list(self):
        base = {'a': [1, 2, 3]}
        left = 'a'
        right = [1]

        DB._remove(base, left, right)
        self.assertEqual(base[left], [2, 3])

    def test_one_from_list_to_single(self):
        base = {'a': [1, 2]}
        left = 'a'
        right = [1]

        DB._remove(base, left, right)
        self.assertEqual(base[left], 2)

    def test_multi_from_list(self):
        base = {'a': [1, 2, 3, 4]}
        left = 'a'
        right = [1, 2]

        DB._remove(base, left, right)
        self.assertEqual(base[left], [3, 4])

    def test_one_from_dict(self):
        base = {'a': {'b': 1, 'c': 2}}
        left = 'a'
        right = ['b']

        DB._remove(base, left, right)
        self.assertEqual(base[left], {'c': 2})

    def test_multi_from_dict(self):
        base = {'a': {'b': 1, 'c': 2}}
        left = 'a'
        right = ['b', 'c']

        DB._remove(base, left, right)
        self.assertEqual(base[left], {})

    def test_error_not_found_single(self):
        base = {'a': 1}
        left = 'a'
        right = 'x'

        with self.assertRaises(DatabaseError):
            DB._remove(base, left, right)

    def test_error_not_found_list(self):
        base = {'a': []}
        left = 'a'
        right = 'x'

        with self.assertRaises(DatabaseError):
            DB._remove(base, left, right)

    def test_error_not_found_dict(self):
        base = {'a': {}}
        left = 'a'
        right = 'x'

        with self.assertRaises(DatabaseError):
            DB._remove(base, left, right)


class TestPop(unittest.TestCase):
    ''' pop '''

    def setUp(self):
        DB.post_action()

    def test_nothing(self):
        ''' nothing to pop, nothing to show and don't write out the db '''
        base = {'a': {}}
        left = 'a'

        DB._pop(base, left)
        self.assertEqual(DB.output, [])
        self.assertFalse(DB.write_needed)

    def test_pop_from_single(self):
        base = {'a': 1}
        left = 'a'

        DB._pop(base, left)
        self.assertEqual(DB.output, ['1'])
        self.assertTrue(left not in base)

    def test_pop_from_list(self):
        base = {'a': [1, 2]}
        left = 'a'

        DB._pop(base, left)
        self.assertEqual(DB.output, ['2'])
        self.assertEqual(base[left], [1])

    def test_pop_from_dict_single(self):
        base = {'a': {'b': 1}}
        left = 'a'

        DB._pop(base, left)
        self.assertEqual(DB.output, ["{'b': 1}"])
        self.assertTrue(left not in base)

    def test_pop_from_dict_multi(self):
        base = {'a': {'b': 1}, 'b': 2}
        left = 'a'

        DB._pop(base, left)
        self.assertEqual(DB.output, ["{'b': 1}"])
        self.assertTrue(left not in base)
        self.assertTrue('b' in base)


if __name__ == '__main__':
    unittest.main()
    DB.writer_running.clear()
