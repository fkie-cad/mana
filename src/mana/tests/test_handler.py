from datetime import datetime
from unittest import mock

from mana.handler import DetectionHandler, Device
from mana.method import Method


class MethodDummy(Method):

    def __init__(self, handler, option1, option2, *args, **kwargs):
        super().__init__(handler, *args, **kwargs)
        self.option1 = option1
        self.option2 = option2

    def detect_spoofing_attack(self, device_id, latest_state, previous_state, state_history):
        return 1


class DetectionHandlerTestable(DetectionHandler):

    def setup_devices(self, device_ids):
        for device_id in device_ids:
            device = Device()
            device.device_id = device_id
            device.state_history = mock.MagicMock()
            device.previous_state = device.state_history.state(0)
            self.devices.append(device)


@mock.patch("mana.nmea_parser.NmeaParser.parse")
def test_detection_handler_handle(parse_mock):
    update_time = datetime(2018, 1, 1, 12, 0)
    device_id = "DEVICE1"
    sentence = "TEST"
    on_spoofing_attack_mock = mock.MagicMock()
    handler = DetectionHandlerTestable(device_ids=[device_id], method_classes=[MethodDummy], method_options={
        "option1": "option1",
        "option2": "option2"
    }, detection_threshold=0.5, on_spoofing_attack=on_spoofing_attack_mock)
    handler.previous_states[(device_id, MethodDummy)] = mock.MagicMock()
    handler.handle(device_id=device_id, time=update_time, sentence=sentence)
    device = handler.device(device_id)
    parse_mock.assert_called_once()
    state_history_mock = device.state_history
    state_history_mock.add_state.assert_called_once()
    on_spoofing_attack_mock.assert_called_with(device_id=device_id, spoofing_indicator=1, method=mock.ANY,
                                               state=mock.ANY)
