#!/usr/bin/env python3

# pylint: disable=protected-access
# pylint: disable=no-self-use
# pylint: disable=missing-docstring
# pylint: disable=too-many-public-methods

import unittest

from apocrypha.datum import Datum

from test_server import TestServerBase, PORT


def datum():
    return Datum(port=PORT)


class TestDatum(TestServerBase):

    def test_init(self):
        datum()

    def test_set_get(self):
        d = datum()
        d['apple'] = 'sauce'

        self.assertEqual(
            str(d['apple']), 'sauce')

    def test_delete(self):
        d = datum()

        d['test_delete'] = 'hello'
        self.assertEqual(
            str(d['test_delete']), 'hello')

        del d['test_delete']

        self.assertEqual(
            d['test_delete'], {})

    def test_iterate(self):
        d = datum()

        in_nums = list(range(0, 10))
        d['numbers'] = in_nums

        nums = []
        for i in d['numbers']:
            nums += [i]

        self.assertListEqual(
            nums, in_nums)

    def test_length_str(self):
        d = datum()
        d['string'] = 'hey' * 10

        self.assertEqual(
            len(d['string']),
            30)

    def test_length_dict(self):
        d = datum()
        d['dict'] = {1: 2, 3: 4}
        self.assertEqual(
            len(d['dict']), 2)

    def test_add_to_nothing(self):
        d = datum()
        d['adding'] += 'hello'

        self.assertEqual(
            str(d['adding']), 'hello')

    def test_add_to_existing(self):
        d = datum()
        d['adding again'] += 'hello'
        d['adding again'] += 'hello'

        self.assertEqual(
            list(d['adding again']), ['hello', 'hello'])

    @unittest.expectedFailure
    def test_keys_integers(self):
        d = datum()
        data = {1: 2, 3: 4, 5: 6}

        d['dict'] = data

        out = []
        for i in d['dict'].keys():
            out += [i]

        self.assertEqual(
            list(data.keys()), out)

    def test_keys_strings(self):
        d = datum()
        data = {'1': 2, '3': 4, '5': 6}

        d['dict'] = data

        out = []
        for i in d['dict'].keys():
            out += [i]

        self.assertListEqual(
            sorted(list(data.keys())), sorted(out))

    def test_append(self):
        d = Datum('appending', port=PORT)
        d.append('a')
        d.append('b')

        self.assertListEqual(
            list(d), ['a', 'b'])

    def test_pop(self):
        d = Datum('popping', port=PORT)
        d.append('a')
        result = d.pop()

        self.assertEqual(result, 'a')



if __name__ == '__main__':
    unittest.main()
