import re
import socket

class EncapFramedSock:               # a facade
  def __init__(self, name):
    self.sock, self.name = name
    self.rbuf = b""         # receive buffer
    print(f"new framed sock: sock={self.sock}, name={self.name}")

  def shutdown(self):
    return self.sock.shutdown(socket.SHUT_WR)
  def close(self):
    return self.sock.close()

  def send(self, payload, debugPrint=0):
    if debugPrint: print("framedSend: sending %d byte message" % len(payload))
    msg = str(len(payload)).encode() + b':' + payload
    while len(msg):
      nsent = self.sock.send(msg)
      msg = msg[nsent:]

  def receive(self, debugPrint=1):
    state = "getLength"
    msgLength = -1
    while True:
      if (state == "getLength"):
        match = re.match(b'([^:]+):(.*)', self.rbuf, re.DOTALL | re.MULTILINE) # look for colon
        if match:
          lengthStr, self.rbuf = match.groups()
          try: 
            msgLength = int(lengthStr)
          except:
            if len(self.rbuf):
              print("badly formed message length:", lengthStr)
              return None
          state = "getPayload"
      if state == "getPayload":
        if len(self.rbuf) >= msgLength:
         payload = self.rbuf[0:msgLength]
         self.rbuf = self.rbuf[msgLength:]
         return payload
      try:
        r = self.sock.recv(100)
        self.rbuf += r
        if len(r) == 0:
          if len(self.rbuf) != 0:
           print("FramedReceive: incomplete message. \n state=%s, length=%d, self.rbuf=%s" % (state, msgLength, self.rbuf))
          return None
      except:
        return None
      if debugPrint: print("FramedReceive: state=%s, length=%d, self.rbuf=%s" % (state, msgLength, self.rbuf))
