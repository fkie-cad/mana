import re
from threading import Thread
from datetime import datetime

from serial import Serial
from scapy.all import sniff
from scapy.layers.inet import UDP, IP

from mana.utility import string_to_datetime


class Feeder:

    def __init__(self, handler):
        self.handler = handler

    def run(self):
        raise NotImplementedError()


class LogFeeder(Feeder):

    def __init__(self, handler, log_file):
        super().__init__(handler)
        self.log_file = log_file
        self.line_format = re.compile('([0-9-]+ +[0-9:.]+) +([a-zA-Z0-9]+) +(.+)')

    def run(self):
        lines = self.read_lines_from_log_file()
        for line in lines:
            match = self.line_format.match(line)
            if not match:
                continue
            time_string, device_id, sentence = match.groups()
            time = string_to_datetime(time_string)
            self.handler.handle(device_id=device_id, time=time, sentence=sentence)

    def read_lines_from_log_file(self):
        with open(self.log_file, 'r') as file:
            return file.readlines()


class SerialFeeder(Feeder):

    def __init__(self, handler, ports):
        super().__init__(handler)
        self.ports = ports

    def run(self):
        for port in self.ports:
            self.create_serial_thread(port)

    def create_serial_thread(self, port):
        thread = SerialThread(self.handler, port)
        thread.run()


class SerialThread(Thread):

    def __init__(self, handler, port, *args, **kwargs):
        super().__init__(*args, *kwargs)
        self.handler = handler
        self.port = port
        self.serial = None
        self.running = True
        self.connect_to_serial_port()

    def run(self):
        while self.is_running():
            sentence = self.read_sentence()
            if len(sentence) == 0:
                continue
            self.handler.handle(device_id=self.port, time=self.current_datetime(), sentence=sentence)

    def is_running(self):
        return self.running

    def read_sentence(self):
        received_bytes = self.read_line_from_serial_connection()
        sentence = received_bytes.decode(errors='ignore')
        sentence = sentence.rstrip()
        return sentence

    def connect_to_serial_port(self):
        self.serial = Serial(self.port, 9600, timeout=.1)

    def read_line_from_serial_connection(self):
        received_bytes = self.serial.readline()
        return received_bytes

    @staticmethod
    def current_datetime():
        return datetime.now()


class PcapFeeder(Feeder):

    def __init__(self, handler, pcap_file):
        super().__init__(handler)
        self.pcap_file = pcap_file

    def run(self):
        sniff(offline=self.pcap_file, prn=self.handle_packet, store=0)

    def handle_packet(self, packet):
        if UDP not in packet or IP not in packet:
            return
        ip_packet = packet[IP]
        udp_packet = packet[UDP]
        ms = packet.time * 1000
        time = datetime.fromtimestamp(ms//1000).replace(microsecond=ms%1000*1000)
        source_ip = ip_packet.src
        payload = bytes(udp_packet.payload)
        sentences = list(filter(None, payload.split(b'\r\n')))
        for sentence in sentences:
            sentence = sentence.decode(errors='ignore')
            self.handler.handle(device_id=source_ip, time=time, sentence=sentence)


class NetworkFeeder(Feeder):

    def __init__(self, handler, interface=None):
        super().__init__(handler)
        self.interface = interface

    def run(self):
        sniff(iface=self.interface, prn=self.handle_packet, store=0)

    def handle_packet(self, packet):
        if UDP not in packet or IP not in packet:
            return
        ip_packet = packet[IP]
        udp_packet = packet[UDP]
        time = datetime.fromtimestamp(packet.time)
        source_ip = ip_packet.src
        payload = bytes(udp_packet.payload)
        sentences = list(filter(None, payload.split(b'\r\n')))
        for sentence in sentences:
            sentence = sentence.decode(errors='ignore')
            self.handler.handle(device_id=source_ip, time=time, sentence=sentence)
