"""Three-channel serial contract. Unknown distance produces zero output."""
import math
import time


def channels_for(markers):
    channels = [0,0,0]
    for m in markers:
        d, angle = m.get('distance_m'), m.get('horizontal_angle_deg')
        if m.get('status') != 'measured_reference' or not isinstance(d,(int,float)) or not isinstance(angle,(int,float)):
            continue
        if not math.isfinite(d) or d <= 0 or not math.isfinite(angle):
            continue
        channel = 0 if angle < -10 else 2 if angle > 10 else 1
        # Obstacle position, NOT a direction to walk. Nearer -> stronger signal.
        channels[channel] = max(channels[channel],round(255*max(0,min(1,(2.0-d)/1.8))))
    return channels


def packet(channels):
    if len(channels)!=3 or any(type(v) is not int or not 0<=v<=255 for v in channels):
        raise ValueError('Expected three integer channels in [0,255]')
    return ('P1,%d,%d,%d\n' % tuple(channels)).encode('ascii')


class SerialBridge:
    def __init__(self, port=None):
        self.connection = None
        self.status = 'preview_only'
        if port:
            import serial
            if port == 'auto':
                from serial.tools import list_ports
                ports = [p.device for p in list_ports.comports() if p.vid in (0x2341,0x2A03,0x1A86,0x10C4)]
                if len(ports)!=1:
                    raise ValueError('Auto needs exactly one Arduino/USB-serial device; specify --serial-port.')
                port=ports[0]
            self.connection=serial.Serial(port,115200,timeout=0.2,write_timeout=0.2)
            time.sleep(2)  # Arduino reset after opening serial
            self.connection.reset_input_buffer()
            self.connection.write(b'HELLO\n')
            if self.connection.readline().strip()!=b'PULSEPATH/1':
                self.connection.close()
                raise ValueError('Board did not identify as PULSEPATH/1; flash the supplied sketch.')
            self.status='connected'

    def send(self, channels):
        if self.connection:
            try:
                self.connection.write(packet(channels))
            except OSError:
                self.status='disconnected'
                self.connection.close()
                self.connection=None

    def close(self):
        self.send([0,0,0])
        if self.connection:
            self.connection.close()
