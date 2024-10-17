import socket
from tango.server import Device, command, attribute, AttrWriteType, device_property
from tango import DevState
from enum import IntEnum
from functools import partial


OUT1 = "Out1"
OUT2 = "Out2"
IN1 = "In1"
IN2 = "In2"

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

OUTPUT_CHANNEL_ATTRIBUTES = dict(
    power=dict(cmd="value", dtype=float),
    setpoint=dict(cmd="PID.setpoint", dtype=float),
    ramp=dict(cmd="PID.Ramp", dtype=float),
    ramp_setpoint=dict(cmd="PID.RampT", dtype=float),
    PID_input=dict(cmd="PID.input", dtype=str),
    PID_mode=dict(cmd="PID.Mode", dtype=PIDMode),
    P=dict(cmd="PID.P", dtype=float),
    I=dict(cmd="PID.I", dtype=float),
    D=dict(cmd="PID.D", dtype=float),
    tune_mode=dict(cmd="Tune.Mode", dtype=TuneMode),
    tune_type=dict(cmd="Tune.Type", dtype=TuneType),
    tune_lag=dict(cmd="Tune.Lag", dtype=float),
    tune_stepY=dict(cmd="Tune.StepY", dtype=float),
)

INPUT_CHANNEL_ATTRIBUTES = dict(
    temperature=dict(cmd="value", dtype=float),
    sensor_type=dict(cmd="sensor", dtype=SensorType),
)

class CryovacTIC500(Device):

    host: str = device_property(doc="Hostname or IP address")
    port: int = device_property(default_value=23)

    def init_device(self) -> None:
        super().init_device()
        self._channel_attrs = {}
        self._channel_attrs.update(OUTPUT_CHANNEL_ATTRIBUTES)
        self._channel_attrs.update(INPUT_CHANNEL_ATTRIBUTES)
        try:
            self.conn = socket.socket()
            self.conn.connect((self.host, self.port))
            self.conn.settimeout(0.5)
            self.set_state(DevState.ON)
            self.send_command("system.com.verbose=high")  # always reply to commands
        except Exception as exc:
            self.set_state(DevState.FAULT)
            self.set_status(str(exc))

    @command
    def query(self, cmd: str) -> str:
        self.conn.send(f"{cmd}\n".encode())
        try:
            ans = self.conn.recv(1024).decode().strip()
        except TimeoutError:  # likely sent command with no reply
            ans = "Timeout. Did you expect a reply?"
        if ans.startswith("Error"):
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
                attr = attribute(
                    name=f"Out{n}.{name}",
                    dtype=conf["dtype"],
                    fget=self.generic_read,
                    fset=self.generic_write,
                )
                self.add_attribute(attr)
        for n in [1, 2, 3, 4]:  # four input channels
            for name, conf in INPUT_CHANNEL_ATTRIBUTES.items():
                attr = attribute(
                    name=f"In{n}.{name}",
                    dtype=conf["dtype"],
                    fget=self.generic_read,
                    fset=self.generic_write,
                )
                self.add_attribute(attr)
    
    def generic_read(self, attr: attribute):
        channel, variable = attr.get_name().split(".")
        cmd = self._channel_attrs[variable]["cmd"]
        dtype = self._channel_attrs[variable]["dtype"]
        ans = self.query(f"{channel}.{cmd}?")
        self.debug_stream(f"generic_read({channel}, {variable}) -> {ans}")
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
        self.debug_stream(f"generic_write({channel}, {variable}, {value})")
        self.query(f"{channel}.{variable}={value}")
