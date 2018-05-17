#!/usr/bin/env python3

# pylint: disable=no-self-use
# pylint: disable=arguments-differ

'''
Experimental client that hides database calls
'''

import collections

from apocrypha.client import Client


class Datum(collections.MutableMapping):
    ''' allows the user to treat a location in the database like a 'normal'
    python variable that behaves mostly like a dict()
    '''

    def __init__(self, *base: [str]) -> None:
        ''' setup, create client
        base is our root in the database
        '''
        self._base = list(base) if base else ['']
        self._client = Client()

    def __repr__(self) -> None:
        ''' get our value for printing
        '''
        return str(self._client.get(*self._base) or {})

    def __getitem__(self, key: str) -> any:
        ''' retrieve a value, returns another Inline for deep indexing
        '''
        return Datum(*self._base + [key])

    def __setitem__(self, key: str, value: any) -> None:
        ''' assign a value
        '''
        self._client.set(*self._base + [key], value=value)

    def __delitem__(self, key: str) -> None:
        ''' delete a key
        '''
        self._client.delete(*self._base + [key])

    def __iter__(self) -> iter:
        ''' iterable for loops
        '''
        return iter(self._client.get(*self._base))

    def __len__(self) -> int:
        return len(self._client.get(*self._base))

    def __keytransform__(self, key: str) -> str:
        return key

    def __add__(self, value: str) -> str:
        ''' show what ourself + value would look like, used by +=
        '''
        result = self._client.get(*self._base, default=[], cast=list)
        return result + [value]

    def keys(self) -> [str]:
        ''' list of keys
        '''
        return self._client.keys(*self._base)

    def pop(self, cast: callable = None) -> any:
        ''' remove last item in list
        '''
        return self._client.pop(*self._base, cast=cast)

    def append(self, value: str) -> None:
        ''' add item to list
        '''
        self._client.append(*self._base, value=value)
