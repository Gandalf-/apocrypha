#!/usr/bin/env python3

'''
Network functions, implements simple protocol that sends the size of the
message before the message
'''

import socket
import struct


def write(sock, message):
    ''' socket, string -> none

    get the length of the message, pack it, prepend to the message and send it
    '''
    try:
        message = struct.pack('>I', len(message)) + message.encode('utf-8')
        sock.sendall(message)

    except (BrokenPipeError, UnicodeDecodeError):
        return False

    else:
        return True


def read(sock):
    ''' socket -> string, none

    read the number of bytes in the message, unpack it, then read that many
    bytes and pass the result back to the caller
    '''

    def _recv_all(n_bytes):
        '''
        read n bytes from a socket
        '''
        data = b''

        while len(data) < n_bytes:
            try:
                fragment = sock.recv(n_bytes - len(data))
            except ConnectionResetError:
                print('lost connection to remote')
                return None

            if not fragment:
                break
            else:
                data += fragment

        return data

    try:
        sock.settimeout(2)

        raw_msg_len = _recv_all(4)
        if not raw_msg_len:
            return None

        msg_len = struct.unpack('>I', raw_msg_len)[0]
        return _recv_all(msg_len).decode('utf-8')

    except socket.timeout:
        return None

    finally:
        sock.settimeout(None)
