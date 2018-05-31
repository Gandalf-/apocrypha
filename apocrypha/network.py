#!/usr/bin/env python3

'''
Network functions, implements simple protocol that sends the size of the
message before the message
'''

import socket
import struct
from typing import Tuple


def write(sock: socket.socket, message: str) -> bool:
    '''
    get the length of the message, pack it, prepend to the message and send it
    '''
    try:
        raw_message = struct.pack('>I', len(message)) + message.encode('utf-8')
        sock.sendall(raw_message)

    except (BrokenPipeError, UnicodeDecodeError):
        return False

    else:
        return True


def read(sock: socket.socket) -> Tuple[str, bool]:
    '''
    read the number of bytes in the message, unpack it, then read that many
    bytes and pass the result back to the caller
    '''
    failure = ('', True)

    raw_msg_len, error = _recv_all(sock, 4)
    if error or not raw_msg_len:
        return failure

    msg_len = struct.unpack('>I', raw_msg_len)[0]
    result, error = _recv_all(sock, msg_len)
    if error:
        return failure

    return result.decode('utf-8'), False


def _recv_all(sock: socket.socket, n_bytes: int) -> Tuple[bytes, bool]:
    '''
    read n bytes from a socket
    '''
    data = b''

    while len(data) < n_bytes:
        try:
            fragment = sock.recv(n_bytes - len(data))
        except ConnectionError:
            print('lost connection to remote')
            return b'', True

        if not fragment:
            break
        else:
            data += fragment

    return data, False
