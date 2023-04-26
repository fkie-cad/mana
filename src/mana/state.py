from copy import deepcopy
from dataclasses import dataclass, field
from datetime import timedelta, datetime as dt
from typing import List


@dataclass
class SatelliteState:
    pseudo_random_noise: str = field(default=None)
    elevation: float = field(default=None)
    azimuth: float = field(default=None)
    carrier_to_noise_density: float = field(default=None)
    is_visible: bool = field(default=False)
    is_active: bool = field(default=False)


@dataclass
class NmeaState:
    update_time: dt = field(default=None)
    last_nmea_sentence: str = field(default=None)
    gps_time: dt = field(default=None)
    latitude: float = field(default=None)
    longitude: float = field(default=None)
    height_above_sea_level: float = field(default=None)
    speed: float = field(default=None)
    course: float = field(default=None)
    magnetic_declination: float = field(default=None)
    geoidal_separation: float = field(default=None)
    positional_dilution_of_precision: float = field(default=None)
    horizontal_dilution_of_precision: float = field(default=None)
    vertical_dilution_of_precision: float = field(default=None)
    gps_quality: float = field(default=None)
    satellites: List[SatelliteState] = field(default_factory=lambda: [])


class StateHistory:

    def __init__(self, max_state_history_time_span=5):
        self.state_history = []
        self.max_state_history_time_span = max_state_history_time_span

    def add_state(self, state):
        state = deepcopy(state)
        self.state_history.insert(0, state)
        reference_time = state.update_time - timedelta(seconds=self.max_state_history_time_span)
        self.state_history = [s for s in self.state_history if s.update_time >= reference_time]

    def state(self, index):
        if len(self.state_history) <= index:
            return None
        state = self.state_history[index]
        return state

    def state_after(self, reference_time):
        for state in reversed(self.state_history):
            if state.update_time >= reference_time:
                return state
        return None

    def state_before(self, reference_time):
        for state in self.state_history:
            if state.update_time <= reference_time:
                return state
        return None
