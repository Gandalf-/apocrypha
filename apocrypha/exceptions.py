#!/usr/bin/env python3

'''
exceptions for other modules
'''


class PeerCreateFailed(Exception):
    '''
    encapsulates the various network errors that can happen while connecting
    '''
    pass


class FailedQuery(Exception):
    ''' notifies the caller that the query failed, the node will handle
    attempting to recover the peer
    '''
    pass


class DatabaseError(Exception):
    ''' used by Apocrypha.error()

    these denote something went wrong with a query, incorrect types, incorrect
    usage, etc
    '''
    pass
