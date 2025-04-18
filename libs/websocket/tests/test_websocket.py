# -*- coding: utf-8 -*-
#
"""

"""

"""
websocket - WebSocket client library for Python

Copyright (C) 2010 Hiroki Ohtani(liris)

    This library is free software; you can redistribute it and/or
    modify it under the terms of the GNU Lesser General Public
    License as published by the Free Software Foundation; either
    version 2.1 of the License, or (at your option) any later version.

    This library is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
    Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public
    License along with this library; if not, write to the Free Software
    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

"""

import sys
sys.path[0:0] = [""]

import os
import os.path
import socket

import six

# websocket-client
import websocket as ws
from websocket._handshake import _create_sec_websocket_key, \
    _validate as _validate_header
from websocket._http import read_headers
from websocket._utils import validate_utf8

if six.PY3:
    from base64 import decodebytes as base64decode
else:
    from base64 import decodestring as base64decode

if sys.version_info[0] == 2 and sys.version_info[1] < 7:
    import unittest2 as unittest
else:
    import unittest

try:
    from ssl import SSLError
except ImportError:
    # dummy class of SSLError for ssl none-support environment.
    class SSLError(Exception):
        pass

# Skip test to access the internet.
TEST_WITH_INTERNET = os.environ.get('TEST_WITH_INTERNET', '0') == '1'
TRACEABLE = True


def create_mask_key(_):
    return "abcd"


class SockMock(object):
    def __init__(self):
        self.data = []
        self.sent = []

    def add_packet(self, data):
        self.data.append(data)

    def gettimeout(self):
        return None

    def recv(self, bufsize):
        if self.data:
            e = self.data.pop(0)
            if isinstance(e, Exception):
                raise e
            if len(e) > bufsize:
                self.data.insert(0, e[bufsize:])
            return e[:bufsize]

    def send(self, data):
        self.sent.append(data)
        return len(data)

    def close(self):
        pass


class HeaderSockMock(SockMock):

    def __init__(self, fname):
        SockMock.__init__(self)
        path = os.path.join(os.path.dirname(__file__), fname)
        with open(path, "rb") as f:
            self.add_packet(f.read())


class WebSocketTest(unittest.TestCase):
    def setUp(self):
        ws.enableTrace(TRACEABLE)

    def tearDown(self):
        pass

    def testDefaultTimeout(self):
        self.assertEqual(ws.getdefaulttimeout(), None)
        ws.setdefaulttimeout(10)
        self.assertEqual(ws.getdefaulttimeout(), 10)
        ws.setdefaulttimeout(None)

    def testWSKey(self):
        key = _create_sec_websocket_key()
        self.assertTrue(key != 24)
        self.assertTrue(six.u("¥n") not in key)

    def testNonce(self):
        """ WebSocket key should be a random 16-byte nonce.
        """
        key = _create_sec_websocket_key()
        nonce = base64decode(key.encode("utf-8"))
        self.assertEqual(16, len(nonce))

    def testWsUtils(self):
        key = "c6b8hTg4EeGb2gQMztV1/g=="
        required_header = {
            "upgrade": "websocket",
            "connection": "upgrade",
            "sec-websocket-accept": "Kxep+hNu9n51529fGidYu7a3wO0="}
        self.assertEqual(_validate_header(required_header, key, None), (True, None))

        header = required_header.copy()
        header["upgrade"] = "http"
        self.assertEqual(_validate_header(header, key, None), (False, None))
        del header["upgrade"]
        self.assertEqual(_validate_header(header, key, None), (False, None))

        header = required_header.copy()
        header["connection"] = "something"
        self.assertEqual(_validate_header(header, key, None), (False, None))
        del header["connection"]
        self.assertEqual(_validate_header(header, key, None), (False, None))

        header = required_header.copy()
        header["sec-websocket-accept"] = "something"
        self.assertEqual(_validate_header(header, key, None), (False, None))
        del header["sec-websocket-accept"]
        self.assertEqual(_validate_header(header, key, None), (False, None))

        header = required_header.copy()
        header["sec-websocket-protocol"] = "sub1"
        self.assertEqual(_validate_header(header, key, ["sub1", "sub2"]), (True, "sub1"))
        self.assertEqual(_validate_header(header, key, ["sub2", "sub3"]), (False, None))

        header = required_header.copy()
        header["sec-websocket-protocol"] = "sUb1"
        self.assertEqual(_validate_header(header, key, ["Sub1", "suB2"]), (True, "sub1"))

        header = required_header.copy()
        self.assertEqual(_validate_header(header, key, ["Sub1", "suB2"]), (False, None))

    def testReadHeader(self):
        status, header, status_message = read_headers(HeaderSockMock("data/header01.txt"))
        self.assertEqual(status, 101)
        self.assertEqual(header["connection"], "Upgrade")

        status, header, status_message = read_headers(HeaderSockMock("data/header03.txt"))
        self.assertEqual(status, 101)
        self.assertEqual(header["connection"], "Upgrade, Keep-Alive")

        HeaderSockMock("data/header02.txt")
        self.assertRaises(ws.WebSocketException, read_headers, HeaderSockMock("data/header02.txt"))

    def testSend(self):
        # TODO: add longer frame data
        sock = ws.WebSocket()
        sock.set_mask_key(create_mask_key)
        s = sock.sock = HeaderSockMock("data/header01.txt")
        sock.send("Hello")
        self.assertEqual(s.sent[0], six.b("\x81\x85abcd)\x07\x0f\x08\x0e"))

        sock.send("こんにちは")
        self.assertEqual(s.sent[1], six.b("\x81\x8fabcd\x82\xe3\xf0\x87\xe3\xf1\x80\xe5\xca\x81\xe2\xc5\x82\xe3\xcc"))

        sock.send(u"こんにちは")
        self.assertEqual(s.sent[1], six.b("\x81\x8fabcd\x82\xe3\xf0\x87\xe3\xf1\x80\xe5\xca\x81\xe2\xc5\x82\xe3\xcc"))

#        sock.send("x" * 5000)
#        self.assertEqual(s.sent[1], six.b("\x81\x8fabcd\x82\xe3\xf0\x87\xe3\xf1\x80\xe5\xca\x81\xe2\xc5\x82\xe3\xcc"))

        self.assertEqual(sock.send_binary(b'1111111111101'), 19)

    def testRecv(self):
        # TODO: add longer frame data
        sock = ws.WebSocket()
        s = sock.sock = SockMock()
        something = six.b("\x81\x8fabcd\x82\xe3\xf0\x87\xe3\xf1\x80\xe5\xca\x81\xe2\xc5\x82\xe3\xcc")
        s.add_packet(something)
        data = sock.recv()
        self.assertEqual(data, "こんにちは")

        s.add_packet(six.b("\x81\x85abcd)\x07\x0f\x08\x0e"))
        data = sock.recv()
        self.assertEqual(data, "Hello")

    @unittest.skipUnless(TEST_WITH_INTERNET, "Internet-requiring tests are disabled")
    def testIter(self):
        count = 2
        for _ in ws.create_connection('wss://stream.meetup.com/2/rsvps'):
            count -= 1
            if count == 0:
                break

    @unittest.skipUnless(TEST_WITH_INTERNET, "Internet-requiring tests are disabled")
    def testNext(self):
        sock = ws.create_connection('wss://stream.meetup.com/2/rsvps')
        self.assertEqual(str, type(next(sock)))

    def testInternalRecvStrict(self):
        sock = ws.WebSocket()
        s = sock.sock = SockMock()
        s.add_packet(six.b("foo"))
        s.add_packet(socket.timeout())
        s.add_packet(six.b("bar"))
        # s.add_packet(SSLError("The read operation timed out"))
        s.add_packet(six.b("baz"))
        with self.assertRaises(ws.WebSocketTimeoutException):
            sock.frame_buffer.recv_strict(9)
        # if six.PY2:
        #     with self.assertRaises(ws.WebSocketTimeoutException):
        #         data = sock._recv_strict(9)
        # else:
        #     with self.assertRaises(SSLError):
        #         data = sock._recv_strict(9)
        data = sock.frame_buffer.recv_strict(9)
        self.assertEqual(data, six.b("foobarbaz"))
        with self.assertRaises(ws.WebSocketConnectionClosedException):
            sock.frame_buffer.recv_strict(1)

    def testRecvTimeout(self):
        sock = ws.WebSocket()
        s = sock.sock = SockMock()
        s.add_packet(six.b("\x81"))
        s.add_packet(socket.timeout())
        s.add_packet(six.b("\x8dabcd\x29\x07\x0f\x08\x0e"))
        s.add_packet(socket.timeout())
        s.add_packet(six.b("\x4e\x43\x33\x0e\x10\x0f\x00\x40"))
        with self.assertRaises(ws.WebSocketTimeoutException):
            sock.recv()
        with self.assertRaises(ws.WebSocketTimeoutException):
            sock.recv()
        data = sock.recv()
        self.assertEqual(data, "Hello, World!")
        with self.assertRaises(ws.WebSocketConnectionClosedException):
            sock.recv()

    def testRecvWithSimpleFragmentation(self):
        sock = ws.WebSocket()
        s = sock.sock = SockMock()
        # OPCODE=TEXT, FIN=0, MSG="Brevity is "
        s.add_packet(six.b("\x01\x8babcd#\x10\x06\x12\x08\x16\x1aD\x08\x11C"))
        # OPCODE=CONT, FIN=1, MSG="the soul of wit"
        s.add_packet(six.b("\x80\x8fabcd\x15\n\x06D\x12\r\x16\x08A\r\x05D\x16\x0b\x17"))
        data = sock.recv()
        self.assertEqual(data, "Brevity is the soul of wit")
        with self.assertRaises(ws.WebSocketConnectionClosedException):
            sock.recv()

    def testRecvWithFireEventOfFragmentation(self):
        sock = ws.WebSocket(fire_cont_frame=True)
        s = sock.sock = SockMock()
        # OPCODE=TEXT, FIN=0, MSG="Brevity is "
        s.add_packet(six.b("\x01\x8babcd#\x10\x06\x12\x08\x16\x1aD\x08\x11C"))
        # OPCODE=CONT, FIN=0, MSG="Brevity is "
        s.add_packet(six.b("\x00\x8babcd#\x10\x06\x12\x08\x16\x1aD\x08\x11C"))
        # OPCODE=CONT, FIN=1, MSG="the soul of wit"
        s.add_packet(six.b("\x80\x8fabcd\x15\n\x06D\x12\r\x16\x08A\r\x05D\x16\x0b\x17"))

        _, data = sock.recv_data()
        self.assertEqual(data, six.b("Brevity is "))
        _, data = sock.recv_data()
        self.assertEqual(data, six.b("Brevity is "))
        _, data = sock.recv_data()
        self.assertEqual(data, six.b("the soul of wit"))

        # OPCODE=CONT, FIN=0, MSG="Brevity is "
        s.add_packet(six.b("\x80\x8babcd#\x10\x06\x12\x08\x16\x1aD\x08\x11C"))

        with self.assertRaises(ws.WebSocketException):
            sock.recv_data()

        with self.assertRaises(ws.WebSocketConnectionClosedException):
            sock.recv()

    def testClose(self):
        sock = ws.WebSocket()
        sock.sock = SockMock()
        sock.connected = True
        sock.close()
        self.assertEqual(sock.connected, False)

        sock = ws.WebSocket()
        s = sock.sock = SockMock()
        sock.connected = True
        s.add_packet(six.b('\x88\x80\x17\x98p\x84'))
        sock.recv()
        self.assertEqual(sock.connected, False)

    def testRecvContFragmentation(self):
        sock = ws.WebSocket()
        s = sock.sock = SockMock()
        # OPCODE=CONT, FIN=1, MSG="the soul of wit"
        s.add_packet(six.b("\x80\x8fabcd\x15\n\x06D\x12\r\x16\x08A\r\x05D\x16\x0b\x17"))
        self.assertRaises(ws.WebSocketException, sock.recv)

    def testRecvWithProlongedFragmentation(self):
        sock = ws.WebSocket()
        s = sock.sock = SockMock()
        # OPCODE=TEXT, FIN=0, MSG="Once more unto the breach, "
        s.add_packet(six.b("\x01\x9babcd.\x0c\x00\x01A\x0f\x0c\x16\x04B\x16\n\x15"
                           "\rC\x10\t\x07C\x06\x13\x07\x02\x07\tNC"))
        # OPCODE=CONT, FIN=0, MSG="dear friends, "
        s.add_packet(six.b("\x00\x8eabcd\x05\x07\x02\x16A\x04\x11\r\x04\x0c\x07"
                           "\x17MB"))
        # OPCODE=CONT, FIN=1, MSG="once more"
        s.add_packet(six.b("\x80\x89abcd\x0e\x0c\x00\x01A\x0f\x0c\x16\x04"))
        data = sock.recv()
        self.assertEqual(
            data,
            "Once more unto the breach, dear friends, once more")
        with self.assertRaises(ws.WebSocketConnectionClosedException):
            sock.recv()

    def testRecvWithFragmentationAndControlFrame(self):
        sock = ws.WebSocket()
        sock.set_mask_key(create_mask_key)
        s = sock.sock = SockMock()
        # OPCODE=TEXT, FIN=0, MSG="Too much "
        s.add_packet(six.b("\x01\x89abcd5\r\x0cD\x0c\x17\x00\x0cA"))
        # OPCODE=PING, FIN=1, MSG="Please PONG this"
        s.add_packet(six.b("\x89\x90abcd1\x0e\x06\x05\x12\x07C4.,$D\x15\n\n\x17"))
        # OPCODE=CONT, FIN=1, MSG="of a good thing"
        s.add_packet(six.b("\x80\x8fabcd\x0e\x04C\x05A\x05\x0c\x0b\x05B\x17\x0c"
                           "\x08\x0c\x04"))
        data = sock.recv()
        self.assertEqual(data, "Too much of a good thing")
        with self.assertRaises(ws.WebSocketConnectionClosedException):
            sock.recv()
        self.assertEqual(
            s.sent[0],
            six.b("\x8a\x90abcd1\x0e\x06\x05\x12\x07C4.,$D\x15\n\n\x17"))

    @unittest.skipUnless(TEST_WITH_INTERNET, "Internet-requiring tests are disabled")
    def testWebSocket(self):
        s = ws.create_connection("ws://echo.websocket.org/")
        self.assertNotEqual(s, None)
        s.send("Hello, World")
        result = s.recv()
        self.assertEqual(result, "Hello, World")

        s.send(u"こにゃにゃちは、世界")
        result = s.recv()
        self.assertEqual(result, "こにゃにゃちは、世界")
        self.assertRaises(ValueError, s.send_close, -1, "")
        s.close()

    @unittest.skipUnless(TEST_WITH_INTERNET, "Internet-requiring tests are disabled")
    def testPingPong(self):
        s = ws.create_connection("ws://echo.websocket.org/")
        self.assertNotEqual(s, None)
        s.ping("Hello")
        s.pong("Hi")
        s.close()

    @unittest.skipUnless(TEST_WITH_INTERNET, "Internet-requiring tests are disabled")
    def testSecureWebSocket(self):
        import ssl
        s = ws.create_connection("wss://api.bitfinex.com/ws/2")
        self.assertNotEqual(s, None)
        self.assertTrue(isinstance(s.sock, ssl.SSLSocket))
        self.assertEqual(s.getstatus(), 101)
        self.assertNotEqual(s.getheaders(), None)
        s.close()

    @unittest.skipUnless(TEST_WITH_INTERNET, "Internet-requiring tests are disabled")
    def testWebSocketWithCustomHeader(self):
        s = ws.create_connection("ws://echo.websocket.org/",
                                 headers={"User-Agent": "PythonWebsocketClient"})
        self.assertNotEqual(s, None)
        s.send("Hello, World")
        result = s.recv()
        self.assertEqual(result, "Hello, World")
        self.assertRaises(ValueError, s.close, -1, "")
        s.close()

    @unittest.skipUnless(TEST_WITH_INTERNET, "Internet-requiring tests are disabled")
    def testAfterClose(self):
        s = ws.create_connection("ws://echo.websocket.org/")
        self.assertNotEqual(s, None)
        s.close()
        self.assertRaises(ws.WebSocketConnectionClosedException, s.send, "Hello")
        self.assertRaises(ws.WebSocketConnectionClosedException, s.recv)


class SockOptTest(unittest.TestCase):
    @unittest.skipUnless(TEST_WITH_INTERNET, "Internet-requiring tests are disabled")
    def testSockOpt(self):
        sockopt = ((socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),)
        s = ws.create_connection("ws://echo.websocket.org", sockopt=sockopt)
        self.assertNotEqual(s.sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY), 0)
        s.close()


class UtilsTest(unittest.TestCase):
    def testUtf8Validator(self):
        state = validate_utf8(six.b('\xf0\x90\x80\x80'))
        self.assertEqual(state, True)
        state = validate_utf8(six.b('\xce\xba\xe1\xbd\xb9\xcf\x83\xce\xbc\xce\xb5\xed\xa0\x80edited'))
        self.assertEqual(state, False)
        state = validate_utf8(six.b(''))
        self.assertEqual(state, True)


if __name__ == "__main__":
    unittest.main()
