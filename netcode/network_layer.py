import json
import socket

from config.constants import *


def local_ip():
    """This machine's LAN address, to tell the other player. Sends nothing."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class NetworkLayer:
    """A non-blocking UDP socket that sends and receives JSON dicts.

    server=True binds to `port` so clients can find it. Clients bind to port 0,
    which lets the OS pick a free port, so a host can run a server *and* its own
    client in one process without the two fighting over the same socket.
    """

    def __init__(self, server=False, port=PORT):
        self.server = server
        self.port = port
        self.socket = None

    def start(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)

        # Windows quirk: if we send to a port nobody is listening on (server not
        # up yet, or a player quit), the *next* recvfrom raises ConnectionReset.
        # Turn that off; UDP has no connection to reset.
        if hasattr(socket, 'SIO_UDP_CONNRESET'):
            self.socket.ioctl(socket.SIO_UDP_CONNRESET, False)

        self.socket.bind(('0.0.0.0', self.port if self.server else 0))
        self.socket.setblocking(False)
        print(f"{'Server' if self.server else 'Client'} socket bound to port {self.socket.getsockname()[1]}")

    def close(self):
        if self.socket:
            self.socket.close()
            self.socket = None

    def send(self, message, address):
        if not self.socket:
            return
        try:
            self.socket.sendto(json.dumps(message).encode(), address)
        except OSError as e:
            print(f"Send to {address} failed: {e}")

    def receive_all(self):
        """Every message waiting right now, as a list of (dict, address)."""
        messages = []
        while self.socket:
            try:
                data, address = self.socket.recvfrom(65536)
            except (BlockingIOError, ConnectionResetError):
                break
            except OSError as e:
                print(f"Socket error: {e}")
                break
            try:
                message = json.loads(data.decode())
            except ValueError:
                continue
            if isinstance(message, dict):
                messages.append((message, address))
        return messages
