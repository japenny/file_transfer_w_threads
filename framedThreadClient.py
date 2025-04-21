#! /usr/bin/env python3

# Echo client program
import socket, sys, re, os, uuid
from threading import Thread

sys.path.append("../lib")       # for params
from lib import params

from encapFramedSock import EncapFramedSock
from archiver import Archiver


class Client(Thread):
    """
    A framed-socket client for archiving and sending files to a remote server.

    Parameters:
        server_host (str): IP address or hostname of the server.
        server_port (int): Port number of the server.
        file_list (list[str]): List of file paths to archive and send.
        debug (bool): If True, prints debug output.
    """

    def __init__(self, server_host, server_port, file_list, debug=False):
        super().__init__()
        self.serverHost = server_host
        self.serverPort = server_port
        self.file_list = file_list
        self.debug = debug

        # Internal:
        self.sock = None
        self.fsock = None
        self.archive_name = None
        self.file_size = 0

    def run(self):
        """
        Main thread: Archive, connect, send and await acknowledgement.
        """
        try:
            self.build_archive()
            self.connect()
            self.send_header()
            self.send_data()
            self.wait_for_ack()
        finally:
            self.cleanup()

    def build_archive(self):
        """
        Archive file(s), and get metadata.
        """
        # Generate a unique name for the archive
        self.archive_name = f"archive_{uuid.uuid4().hex[:8]}.tar"
        archiver = Archiver()
        archiver.archive(self.archive_name, self.file_list)

        # Get file size
        self.file_size = os.path.getsize(self.archive_name)
        if self.debug:
            print(f"[build_archive] Created '{self.archive_name}' with size={self.file_size} bytes")

    def connect(self):
        """
        Create a socket connection to the remote server.
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.serverHost, self.serverPort))
        if self.debug:
            print(f"[connect] Connected to {(self.serverHost, self.serverPort)}")

        self.fsock = EncapFramedSock((self.sock, self.sock.getsockname()))

    def send_header(self):
        """
        Send the archive name and size in one frame.
        """
        header = f"{self.archive_name}\n{self.file_size}\n".encode()
        self.fsock.send(header, debugPrint=self.debug)
        if self.debug:
            print("[send_header] Sent header frame")

    def send_data(self):
        """
        Stream the archive contents in multiple frames.
        """
        fd_in = os.open(self.archive_name, os.O_RDONLY)
        total_sent = 0

        try:
            while True:
                chunk = os.read(fd_in, 4096)
                if not chunk: # End of file
                    break
                self.fsock.send(chunk, debugPrint=self.debug)
                total_sent += len(chunk)
                if self.debug:
                    print(f"[send_data] Sent {total_sent}/{self.file_size} bytes")
        finally:
            os.close(fd_in)

    def wait_for_ack(self):
        """
        Wait for final acknowledgement from server.
        """
        self.fsock.shutdown()  # server can read EOF
        ack = self.fsock.receive(debugPrint=self.debug)
        if ack:
            print("[wait_for_ack] Server says:", ack.decode().strip())

    def cleanup(self):
        """
        Close framed socket.
        """
        self.fsock.close()
        if self.debug:
            print("[cleanup] Closed socket and done")

def main():
    """
    Parse command-line arguments and start the client thread.

    Init:
        -s / --server (str): Server in host:port format.
        -f / --files (str): Space-separated list of files to send.
        -d / --debug (flag): Enable debug output.
        -? / --usage (flag): Show usage.
    """
    # Define command-line arguments and parse them
    switchesVarDefaults = (
        (('-s', '--server'), 'server', "127.0.0.1:50001"),
        (('-f', '--files'),  'files',  False),
        (('-d', '--debug'),  'debug',  False),
        (('-?', '--usage'),  'usage',  False),
    )
    paramMap = params.parseParams(switchesVarDefaults)
    server  = paramMap["server"]
    files   = paramMap["files"]
    debug   = paramMap["debug"]
    usage   = paramMap["usage"]
    print('')
    if usage or (files is None):
        print("Usage: -s host:port -f 'file1 file2 ...'")
        params.usage()

    # Split file list string into a Python list
    if not isinstance(files, list):
        files = files.split()

    try:
        serverHost, serverPort = re.split(":", server)
        serverPort = int(serverPort)
    except:
        print(f"Invalid server format: '{server}'. Expected host:port")
        sys.exit(1)

    # Create and run client
    client = Client(serverHost, serverPort, files, debug=debug)
    client.start()
    client.join()

if __name__ == "__main__":
    main()