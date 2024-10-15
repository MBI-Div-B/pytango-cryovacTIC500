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



class CryovacTIC500Base:

    def query(self, cmd: str) -> str:
        raise NotImplementedError
    
    def send_command(self, cmd: str) -> None:
        raise NotImplementedError

    def get_channel_value(self, channel: str) -> float:
        ans = self.query(f"{channel}.value?")
        return float(ans)
    
    def set_channel_value(self, channel: str, value: float) -> None:
        self.send_command(f"{channel}.value={value:.5f}")
    
    def get_PID_input(self, channel: str) -> str:
        ans = self.query(f"{channel}.PID.Input")
        return ans
    
    def set_PID_input(self, channel: str, value: str) -> None:
        self.send_command(f"Out{channel}.PID.Input=({value})")
    
    def get_PID_setpoint(self, channel: str) -> float:
        ans = self.query(f"{channel}.PID.Input")
        return float(ans)
    
    def set_PID_setpoint(self, channel: str, value: float) -> None:
        self.send_command(f"Out{channel}.PID.Input=({value})")
    
    def get_PID_ramp_setpoint(self, channel: str) -> float:
        ans = self.query(f"{channel}.PID.RampT")
        return float(ans)
    
    def get_PID_ramp_rate(self, channel: str) -> float:
        ans = self.query(f"{channel}.PID.Ramp")
    
    def set_PID_ramp_rate(self, channel: str, value: float) -> None:
        self.send_command(f"{channel}.PID.Ramp={value}")

    def get_PID_on(self, channel: str) -> bool:
        ans = self.query(f"{channel}.PID.mode")
        return ans.lower() == "on"

    def set_PID_on(self, channel, value: bool) -> None:
        mode = "on" if value else "off"
        self.send_command(f"{channel}.PID.mode={mode}")
    
    def get_PID_parameter(self, channel: str, parameter: str) -> float:
        ans = self.query(f"{channel}.PID.{parameter}?")
        return float(ans)
    
    def set_PID_parameter(self, channel: str, parameter: str, value: float) -> None:
        ans = self.send_command(f"{channel}.PID.{parameter}={value}")
    
    def get_sensor_type(self, channel: str) -> SensorType:
        ans = self.query(f"{channel}.Sensor?")
        return SensorType[ans]
    
    def set_sensor_type(self, channel: str, value: SensorType) -> None:
        self.send_command(f"{channel}.Sensor={value.name}")


class CryovacTIC500(CryovacTIC500Base, Device):

    host: str = device_property(doc="Hostname or IP address")
    port: int = device_property(default_value=23)

    # output1_on: bool = attribute()
    output1_value: float = attribute(
        fget=partial(CryovacTIC500Base.get_channel_value, channel=OUT1),
        fset=partial(CryovacTIC500Base.set_channel_value, channel=OUT1),
        doc="Heater output power",
        unit="W",
    )
    output1_setpoint: float = attribute(
        doc="Temperature setpoint",
        unit="K",
        fget=partial(CryovacTIC500Base.get_PID_setpoint, channel=OUT1),
        fset=partial(CryovacTIC500Base.set_PID_setpoint, channel=OUT1),
    )
    output1_ramp_setpoint: float = attribute(
        doc="Momentary setpoint, determined by internal ramp",
        unit="K",
        fget=partial(CryovacTIC500Base.get_PID_ramp_setpoint, channel=OUT1),
    )
    output1_ramp_rate: float = attribute(
        doc="Zero disables ramping",
        unit="K/s",
        fget=partial(CryovacTIC500Base.get_PID_ramp_rate, channel=OUT1),
        fset=partial(CryovacTIC500Base.set_PID_ramp_rate, channel=OUT1),
        )
    output1_PID_on: bool = attribute(
        doc="PID control enabled (True) or disabled (False)",
        fget=partial(CryovacTIC500Base.get_PID_on, channel=OUT1),
        fset=partial(CryovacTIC500Base.set_PID_on, channel=OUT1)
    )
    output1_P: float = attribute(
        fget=partial(CryovacTIC500Base.get_PID_parameter, channel=OUT1, parameter="P"),
        fset=partial(CryovacTIC500Base.set_PID_parameter, channel=OUT1, parameter="P"),
    )
    output1_I: float = attribute(
        fget=partial(CryovacTIC500Base.get_PID_parameter, channel=OUT1, parameter="I"),
        fset=partial(CryovacTIC500Base.set_PID_parameter, channel=OUT1, parameter="I"),
    )
    output1_D: float = attribute(
        fget=partial(CryovacTIC500Base.get_PID_parameter, channel=OUT1, parameter="D"),
        fset=partial(CryovacTIC500Base.set_PID_parameter, channel=OUT1, parameter="D"),
    )
    output1_control_channel: str = attribute(
        doc="Input channel number to be used as PID control input",
        fget=partial(CryovacTIC500Base.get_PID_input, channel=OUT1),
        fset=partial(CryovacTIC500Base.set_PID_input, channel=OUT1),
    )
    input1_type: SensorType = attribute(
        doc="Sensor type",
        fget=partial(CryovacTIC500Base.get_sensor_type, channel=IN1),
        fset=partial(CryovacTIC500Base.set_sensor_type, channel=IN1),
    )
    input1_value: float = attribute(
        fget=partial(CryovacTIC500Base.get_channel_value, channel=IN1),
        doc="Sensor input reading",
        unit="K",
    )

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
    
    