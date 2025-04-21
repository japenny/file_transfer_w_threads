#! /usr/bin/env python3

import sys
sys.path.append("../lib")       # for params
import re, socket, os
from lib import params
from threading import Thread
from encapFramedSock import EncapFramedSock
from archiver import Archiver

class Server(Thread):
    """
    A threaded server that uses a framed-socket to receive an archive file.
    Handles:
      1) Parsing header (archive name and size),
      2) Receiving streamed archive data,
      3) Saving to disk and extracting it.

    Init:
        sock_and_name (tuple): Tuple of socket object and client name/address.
        debug (bool): Whether to print debug messages.
    """

    def __init__(self, sock_and_name, debug):
        super().__init__()
        self.sock, self.name = sock_and_name
        self.fsock = EncapFramedSock((self.sock, self.name))
        self.debug = debug

        # Internal State
        self.state = 'header' # 'header' or 'data'
        self.buffer = b""

        self.archive_name = None
        self.file_size = 0
        self.received = 0
        self.fd_out = None

    def run(self):
        """
        Main server loop:
        - Recieves frames
        - Handle header and data based on state
        """
        print(f"New thread handling connection from {self.name}")
        while True:
            payload = self.fsock.receive(self.debug)
            if not payload:
                print(f"[{self.name}] No more data, connection closed.")
                self.cleanup()
                return

            # Add payload to buffer
            self.buffer += payload

            # Dispatch to header/data logic
            if self.state == 'header':
                self.handle_header()
            if self.state == 'data':
                self.handle_data()

    def handle_header(self):
        """
        Parse the header containing filename and file size.

        returns:
            None
        """
        parts = self.buffer.split(b'\n', 2)
        if len(parts) < 3:
            # Not enough data for two header + remainder
            return
        name_bytes, size_bytes, remainder = parts

        self.archive_name = name_bytes.decode().strip()
        self.file_size = int(size_bytes.decode().strip())
        if self.debug:
            print(f"[{self.name}] Header => archive_name={self.archive_name}, file_size={self.file_size}")

        # Prepare for writing data
        self.fd_out = open('new_' + self.archive_name, 'wb')
        self.received = len(remainder)

        # Update state and add remaining data to buffer
        self.buffer = remainder
        self.state = 'data'

        self.handle_data()

    def handle_data(self):
        """
        Handle incoming archive data and extract when complete.

        returns:
            None
        """

        # Read all bytes in buffer
        while self.buffer and self.received < self.file_size:
            needed = self.file_size - self.received
            chunk = self.buffer[:needed]
            self.fd_out.write(chunk)
            self.received += len(chunk)
            self.buffer = self.buffer[len(chunk):]

        # Once all bytes are read
        if self.received >= self.file_size:
            self.fd_out.close()
            print(f"Archive '{self.archive_name}' saved. Extracting...")

            Archiver().extract(self.archive_name)

            # Send completion msg and cleanup
            print("Extraction complete.")
            ack_msg = f"Received and extracted {self.archive_name}\n"
            self.fsock.send(ack_msg.encode(), self.debug)

            self.cleanup()

    def cleanup(self):
        """Clean up resources: close file if open, and close socket."""
        if self.fd_out and not self.fd_out.closed:
            self.fd_out.close()
        self.fsock.close()

def main():
    """
    Start the threaded archive server.

    Args:
        -l / --listenPort (int): Port to listen on.
        -d / --debug (flag): Enable debug output.
        -? / --usage (flag): Show usage information.

    Returns:
        None
    """
    switchesVarDefaults = (
        (('-l', '--listenPort'), 'listenPort', 50001),
        (('-d', '--debug'), "debug", False),
        (('-?', '--usage'), "usage", False),
    )

    paramMap = params.parseParams(switchesVarDefaults)

    debug, listenPort = paramMap['debug'], paramMap['listenPort']

    if paramMap['usage']:
        params.usage()

    # Create the listening socket
    lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    bind_addr = ("localhost", listenPort)
    lsock.bind(bind_addr)
    print(f"Listening on: {bind_addr}")

    # Accept client connections and create handler threads
    while True:
        sock_addr = lsock.accept()
        server = Server(sock_addr, debug)
        server.start()

if __name__ == "__main__":
    main()
