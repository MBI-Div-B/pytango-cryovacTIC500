import socket
from tango.server import Device, command, attribute, AttrWriteType, device_property
from tango import DevState

class CryovacTIC500(Device):

    host: str = device_property(doc="Hostname or IP address")
    port: int = device_property(default_value=23)

    def init_device(self) -> None:
        super().init_device()
        try:
            self.conn = socket.socket()
            self.conn.connect((self.host, self.port))
            self.conn.settimeout(0.5)
            self.set_state(DevState.ON)
        except Exception as exc:
            self.set_state(DevState.FAULT)
            self.set_status(str(exc))

    @command
    def query(self, cmd: str) -> str:
        self.conn.send(f"{cmd}\n".encode())
        ans = self.conn.recv(1024)
        return ans.decode().strip()
    
    def delete_device(self) -> None:
        self.conn.close()
