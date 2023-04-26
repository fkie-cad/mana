from datetime import datetime

from mana.nmea_parser import NmeaParser, InvalidNmeaSentenceException, NmeaSentenceNotSupportedException
from mana.state import NmeaState, StateHistory
from mana.utility import is_state_different, is_state_sufficiently_defined


class Handler:

    def handle(self, device_id, time, sentence):
        raise NotImplementedError()


class LoggingHandler(Handler):

    def __init__(self, filename=None):
        self.filename = filename or self.current_datetime().strftime('%Y%m%d%H%M%S.log')
        self.file = open(self.filename, 'wb')

    def handle(self, device_id, time, sentence):
        time_string = time.strftime('%Y-%m-%d %H:%M:%S.%f')
        entry = '{time} {device_id} {sentence}\r\n'.format(time=time_string, device_id=device_id, sentence=sentence)
        self.file.write(entry.encode())
        self.file.flush()

    @staticmethod
    def current_datetime():
        return datetime.now()


class Device:
    device_id = None
    state_history = None
    previous_state = None


class StateHistoryHandler(Handler):

    def __init__(self, device_ids):
        super().__init__()
        self.devices = []
        self.setup_devices(device_ids)

    def handle(self, device_id, time, sentence):
        device = self.device(device_id)
        if device is None:
            return
        device = self.device(device_id)
        state_history = device.state_history
        latest_state = state_history.state(0)
        if latest_state is None:
            latest_state = NmeaState()
        try:
            latest_state = NmeaParser.parse(latest_state, time, sentence)
        except (InvalidNmeaSentenceException, NmeaSentenceNotSupportedException):
            return
        state_history.add_state(latest_state)
        self.handle_state(device_id, latest_state, state_history)

    def handle_state(self, device_id, latest_state, state_history):
        raise NotImplementedError()

    def device(self, device_id):
        for device in self.devices:
            if device.device_id == device_id:
                return device
        return None

    def setup_devices(self, device_ids):
        for device_id in device_ids:
            device = Device()
            device.device_id = device_id
            device.state_history = StateHistory()
            device.previous_state = device.state_history.state(0)
            self.devices.append(device)


class DetectionHandler(StateHistoryHandler):

    def __init__(self, device_ids, method_classes, method_options, detection_threshold, on_spoofing_attack):
        super().__init__(device_ids)
        self.detection_threshold = detection_threshold
        self.on_spoofing_attack = on_spoofing_attack
        self.methods = []
        self.previous_states = {}
        self.setup_methods(method_classes, method_options)

    def handle_state(self, device_id, latest_state, state_history):
        for method in self.methods:
            if not is_state_sufficiently_defined(latest_state, method.required_state_fields):
                continue
            previous_states_key = (device_id, type(method))
            previous_state = None
            if previous_states_key in self.previous_states:
                previous_state = self.previous_states[previous_states_key]
            if previous_state is not None \
                    and not is_state_different(latest_state, previous_state, method.variable_state_fields):
                continue
            sufficient_satellite_state_count = 0
            for satellite_state in latest_state.satellites:
                if is_state_sufficiently_defined(satellite_state, method.required_satellite_state_fields):
                    sufficient_satellite_state_count += 1
            if sufficient_satellite_state_count < method.min_sufficient_satellite_state_count:
                continue
            self.previous_states[previous_states_key] = latest_state
            if previous_state is None:
                continue
            spoofing_indicator = method.spoofing_indicator(device_id, latest_state, previous_state, state_history)
            if spoofing_indicator <= self.detection_threshold:
                continue
            self.on_spoofing_attack(device_id=device_id, spoofing_indicator=spoofing_indicator, method=method,
                                    state=latest_state)

    def setup_methods(self, method_classes, method_options):
        for method_class in method_classes:
            method = method_class(self, **method_options)
            self.methods.append(method)
