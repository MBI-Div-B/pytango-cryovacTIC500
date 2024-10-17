import socket
from tango.server import Device, command, attribute, AttrWriteType, device_property
from tango import DevState
from enum import IntEnum
from functools import partial


class SensorType(IntEnum):
    RTD = 0
    Thermistor = 1
    Diode = 2
    ROX = 3

class TuneMode(IntEnum):
    Off = 0
    Auto = 1
    Step = 2
    Relay = 3

class TuneType(IntEnum):
    Conservative = 0
    Moderate = 1
    Aggressive = 2
    Auto = 3

class PIDMode(IntEnum):
    Off = 0
    On = 1
    # Follow = 2

RO = AttrWriteType.READ
RW = AttrWriteType.READ_WRITE

# by default, access is READ_WRITE
OUTPUT_CHANNEL_ATTRIBUTES = dict(
    power=dict(cmd="Value", dtype=float),
    setpoint=dict(cmd="pid.Setpoint", dtype=float),
    ramp=dict(cmd="pid.Ramp", dtype=float),
    ramp_setpoint=dict(cmd="pid.Ramp T", dtype=float, access=RO),
    PID_input=dict(cmd="pid.Input", dtype=str),
    PID_mode=dict(cmd="pid.Mode", dtype=PIDMode),
    P=dict(cmd="pid.P", dtype=float),
    I=dict(cmd="pid.I", dtype=float),
    D=dict(cmd="pid.D", dtype=float),
    tune_mode=dict(cmd="tune.Mode", dtype=TuneMode),
    tune_type=dict(cmd="tune.Type", dtype=TuneType),
    tune_lag=dict(cmd="tune.Lag", dtype=float),
    tune_stepY=dict(cmd="tune.Step Y", dtype=float),
)

INPUT_CHANNEL_ATTRIBUTES = dict(
    temperature=dict(cmd="Value", dtype=float, access=RO),
    sensor_type=dict(cmd="Sensor", dtype=SensorType),
)

class CryovacTIC500(Device):

    host: str = device_property(doc="Hostname or IP address")
    port: int = device_property(default_value=23)

    output_on: bool = attribute()

    def init_device(self) -> None:
        super().init_device()
        self._channel_attrs = {}
        self._channel_attrs.update(OUTPUT_CHANNEL_ATTRIBUTES)
        self._channel_attrs.update(INPUT_CHANNEL_ATTRIBUTES)
        try:
            self.conn = socket.socket()
            self.conn.connect((self.host, self.port))
            self.conn.settimeout(0.5)
            self.ensure_verbose_communication()
            self.set_state(DevState.ON)
        except Exception as exc:
            self.set_state(DevState.FAULT)
            self.set_status(str(exc))
    
    def read_output_on(self) -> bool:
        ans = self.query("outputEnable?")
        return "OutputEnable = On" in ans

    def write_output_on(self, value: bool) -> None:
        val = "on" if value else "off"
        ans = self.query(f"outputEnable = {val}")

    @command
    def query(self, cmd: str) -> str:
        self.conn.send(f"{cmd}\n".encode())
        ans = self.conn.recv(1024).decode().strip()
        self.debug_stream(f"query({cmd}) -> {ans}")
        if ans.startswith("Error"):
            self.error_stream(ans)
            raise RuntimeError(ans)
        return ans
    
    @command
    def send_command(self, cmd: str) -> None:
        self.conn.send(f"{cmd}\n".encode())
    
    @command
    def get_description(self) -> str:
        return self.query("description")
    
    def delete_device(self) -> None:
        self.conn.close()
    
    def initialize_dynamic_attributes(self):
        for n in [1, 2]:  # two output channels
            for name, conf in OUTPUT_CHANNEL_ATTRIBUTES.items():
                access = conf.get("access", RW)
                fset = self.generic_write if access == RW else None
                attr = attribute(
                    name=f"Out{n}.{name}",
                    dtype=conf["dtype"],
                    fget=self.generic_read,
                    fset=fset,
                )
                self.add_attribute(attr)
        for n in [1, 2, 3, 4]:  # four input channels
            for name, conf in INPUT_CHANNEL_ATTRIBUTES.items():
                access = conf.get("access", RW)
                fset = self.generic_write if access == RW else None
                attr = attribute(
                    name=f"In{n}.{name}",
                    dtype=conf["dtype"],
                    fget=self.generic_read,
                    fset=fset,
                )
                self.add_attribute(attr)
    
    def ensure_verbose_communication(self):
        ans = self.query("system.com.verbose?")
        if not "High" in ans:
            self.info_stream("Setting device communication to verbose.")
            self.send_command(f"system.com.verbose=high")
        else:
            self.info_stream("Device communication is verbose.")
    
    def generic_read(self, attr: attribute):
        channel, variable = attr.get_name().split(".")
        cmd = self._channel_attrs[variable]["cmd"]
        dtype = self._channel_attrs[variable]["dtype"]
        ans = self.query(f"({channel}.{cmd}?)")
        
        cmd_ret, ans = [s.strip() for s in ans.split("=")]
        self.debug_stream(f"generic_read -> {ans}")
        if not cmd_ret.endswith(cmd):
            self.warn_stream(
                f"Received reply does not match command: {cmd} -> {cmd_ret}"
            )
        
        if issubclass(dtype, IntEnum):
            return dtype[ans]
        else:
            return dtype(ans)
    
    def generic_write(self, attr: attribute) -> None:
        channel, variable = attr.get_name().split(".")
        value = attr.get_write_value()
        cmd = self._channel_attrs[variable]["cmd"]
        dtype = self._channel_attrs[variable]["dtype"]
        if issubclass(dtype, IntEnum):
            value = dtype(value).name
        ans = self.query(f"({channel}.{cmd})=({value})")
        cmd_ret, ans = [s.strip() for s in ans.split("=")]
        if cmd != cmd_ret:
            self.warn_stream(
                f"Received reply does not match command: {cmd} -> {cmd_ret}"
            )
