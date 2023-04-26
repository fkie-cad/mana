from collections import namedtuple
from datetime import datetime
from unittest import mock

import pytest

from mana.handler import Device
from mana.method import Method, AverageMethod, OrGroupMethod, AndGroupMethod, AverageGroupMethod, \
    MultipleReceiversMethod, PhysicalSpeedLimitMethod, PhysicalRateOfTurnLimitMethod, PhysicalHeightLimitMethod, \
    PhysicalEnvironmentLimitMethod, OrbitPositionsMethod, TimeDriftMethod, CarrierToNoiseDensityMethod
from mana.state import StateHistory, NmeaState, SatelliteState


class StateHistoryDummy:

    def state(self, _index):
        return None


class HandlerDummy:

    def __init__(self, devices=None):
        self.devices = devices or []

    def device(self, device_id):
        for device in self.devices:
            if device.device_id == device_id:
                return device
        return None


@mock.patch('mana.method.method.Method.detect_spoofing_attack')
def test_method_spoofing_indicator(detect_spoofing_attack_mock):
    handler = HandlerDummy()
    state_history = StateHistoryDummy()
    method = Method(handler)
    for a, b in [(1, 1), (0, 0), (1, 1)]:
        detect_spoofing_attack_mock.return_value = a
        spoofing_indicator = method.spoofing_indicator(device_id='DEVICE1', latest_state=None,
                                                       previous_state=None, state_history=state_history)
        assert spoofing_indicator == b


def test_average_method_default_parameters():
    handler = HandlerDummy()
    average_method = AverageMethod(handler)
    assert average_method.max_previous_spoofing_indicators_count == 100


class MethodDummy(Method):
    static_spoofing_indicator = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def detect_spoofing_attack(self, device_id, latest_state, previous_state, state_history):
        return self.static_spoofing_indicator


class AMethodDummy(MethodDummy):
    static_spoofing_indicator = 0.2


class BMethodDummy(MethodDummy):
    static_spoofing_indicator = 0.8


class CMethodDummy(MethodDummy):
    static_spoofing_indicator = 1


@mock.patch('mana.method.method.AverageMethod.detect_spoofing_attack')
def test_average_method_spoofing_indicator(detect_spoofing_attack_mock):
    handler = HandlerDummy()
    state_history = StateHistoryDummy()
    average_method = AverageMethod(handler)

    for a, b in [(1, 0.01), (0, 0.01), (1, 0.02), (1, 0.03), (0, 0.03), (0, 0.03), (1, 0.04), (0, 0.04)]:
        detect_spoofing_attack_mock.return_value = a
        spoofing_indicator = average_method.spoofing_indicator(device_id='DEVICE1', latest_state=None,
                                                               previous_state=None, state_history=state_history)
        assert spoofing_indicator == b


def test_or_and_average_group_method_spoofing_indicator():
    methods = [AMethodDummy, BMethodDummy, CMethodDummy]
    handler = HandlerDummy()
    state_history = StateHistoryDummy()
    or_group_method = OrGroupMethod(handler, methods)
    spoofing_indicator = or_group_method.spoofing_indicator(device_id='DEVICE1', latest_state=None,
                                                            previous_state=None, state_history=state_history)
    assert spoofing_indicator == 1
    and_group_method = AndGroupMethod(handler, methods)
    spoofing_indicator = and_group_method.spoofing_indicator(device_id='DEVICE1', latest_state=None,
                                                             previous_state=None, state_history=state_history)
    assert spoofing_indicator == 0.2
    average_group_method = AverageGroupMethod(handler, methods)
    spoofing_indicator = average_group_method.spoofing_indicator(device_id='DEVICE1', latest_state=None,
                                                                 previous_state=None, state_history=state_history)
    assert spoofing_indicator == pytest.approx(0.66666666)


def test_multiple_receivers_method_default_parameters():
    handler = HandlerDummy()
    multiple_receivers_method = MultipleReceiversMethod(handler, distances={}, distance_ratio_thresholds={})
    assert multiple_receivers_method.new_measurement_weight == 0.1


MultipleReceiversMethodStateDummy = namedtuple('NmeaState', ['update_time', 'gps_time', 'latitude', 'longitude'])


@pytest.mark.parametrize('data_port1,data_port2,expected_spoofing_indicator', [
    ([(1, 0, 0)], [(1, 0, 0)], 1),
    ([(1, 1, 1)], [(1, 0, 0)], 0),
    ([(1, 0.00001, 0)], [(1, 0.00001, 0)], 1),
    ([(1, 0.0000175, 0)], [(1, 0.00001, 0)], 0),
    ([(1, 0, 1)], [(0, 0, 0), (2, 0, 2)], 1),  # Test the linear state approximation
    ([(1, 1, 1)], [(0, 0, 0), (2, 2, 2)], 1),
    ([(1, 0, 1 - 0.0000175)], [(0, 0, 0), (2, 0, 2)], 0),
])
def test_multiple_receivers_method_detect_spoofing_attack(data_port1, data_port2, expected_spoofing_indicator):
    state_history1 = create_state_history_with_multiple_receivers_method_dummy_states(data_port1)
    state_history2 = create_state_history_with_multiple_receivers_method_dummy_states(data_port2)
    device1 = Device()
    device1.device_id = 'DEVICE1'
    device1.state_history = state_history1
    device2 = Device()
    device2.device_id = 'DEVICE2'
    device2.state_history = state_history2
    handler = HandlerDummy(devices=[device1, device2])
    distances = {('DEVICE1', 'DEVICE2'): 1}
    distance_ratio_thresholds = {('DEVICE1', 'DEVICE2'): 0.5}
    method = MultipleReceiversMethod(handler, distances=distances, distance_ratio_thresholds=distance_ratio_thresholds,
                                     new_measurement_weight=1)
    spoofing_indicator = method.detect_spoofing_attack(device_id='DEVICE1',
                                                       latest_state=state_history1.state(0),
                                                       previous_state=state_history1.state(1),
                                                       state_history=state_history1)
    assert spoofing_indicator == expected_spoofing_indicator


def create_state_history_with_multiple_receivers_method_dummy_states(data):
    state_history = StateHistory()
    for seconds, latitude, longitude in data:
        state_dummy = NmeaState(update_time=datetime(2018, 1, 1, 0, 0, seconds),
                                gps_time=datetime(2018, 1, 1, 0, 0, seconds),
                                latitude=latitude, longitude=longitude)
        state_history.add_state(state_dummy)
    return state_history


@pytest.mark.parametrize('speed,expected_spoofing_indicator', [
    (0, 0), (50, 0), (50.1, 1)
])
def test_physical_speed_limit_method_detect_spoofing_attack(speed, expected_spoofing_indicator):
    handler = HandlerDummy()
    state_history = StateHistory()
    latest_state = NmeaState(update_time=datetime(2018, 1, 1, 0, 0, 0), speed=speed)
    state_history.add_state(latest_state)
    method = PhysicalSpeedLimitMethod(handler, max_speed=50)
    spoofing_indicator = method.detect_spoofing_attack(device_id='DEVICE1', latest_state=latest_state,
                                                       previous_state=None, state_history=state_history)
    assert spoofing_indicator == expected_spoofing_indicator


@pytest.mark.parametrize('speed,course,expected_spoofing_indicator', [
    (1, 0, 0), (1, 10, 0), (1, 10.1, 1), (0, 10.1, 0)
])
def test_physical_rate_of_turn_limit_method_detect_spoofing_attack(speed, course, expected_spoofing_indicator):
    handler = HandlerDummy()
    state_history = StateHistory()
    time1 = datetime(2018, 1, 1, 0, 0, 0)
    previous_state = NmeaState(update_time=time1, gps_time=time1, course=0, speed=speed)
    state_history.add_state(previous_state)
    time2 = datetime(2018, 1, 1, 0, 0, 2)
    latest_state = NmeaState(update_time=time2, gps_time=time2, course=course, speed=speed)
    state_history.add_state(latest_state)
    method = PhysicalRateOfTurnLimitMethod(handler, max_rate_of_turn=5, min_speed_to_determine_rate_of_turn=0.5)
    spoofing_indicator = method.detect_spoofing_attack(device_id='DEVICE1', latest_state=latest_state,
                                                       previous_state=previous_state, state_history=state_history)
    assert spoofing_indicator == expected_spoofing_indicator


@pytest.mark.parametrize('height,expected_spoofing_indicator', [
    (-5, 0), (0, 0), (5, 0), (-5.1, 1), (5.1, 1)
])
def test_physical_height_limit_method_detect_spoofing_attack(height, expected_spoofing_indicator):
    handler = HandlerDummy()
    state_history = StateHistory()
    latest_state = NmeaState(update_time=datetime(2018, 1, 1, 0, 0, 0), height_above_sea_level=height)
    state_history.add_state(latest_state)
    method = PhysicalHeightLimitMethod(handler, min_height=-5, max_height=5)
    spoofing_indicator = method.detect_spoofing_attack(device_id='DEVICE1', latest_state=latest_state,
                                                       previous_state=None, state_history=state_history)
    assert spoofing_indicator == expected_spoofing_indicator


class WorldMapDummy():

    def __init__(self):
        self.static_is_on_land = False
        self.static_is_on_water = True

    def is_on_land(self, *_args, **_kwargs):
        return self.static_is_on_land

    def is_on_water(self, *_args, **_kwargs):
        return self.static_is_on_water


class PhysicalEnvironmentLimitMethodTestable(PhysicalEnvironmentLimitMethod):

    def load_world_map(self):
        self.water_map = WorldMapDummy()


@pytest.mark.parametrize('is_on_water,is_on_land,on_water,on_land,expected_spoofing_indicator', [
    (False, False, True, True, 0),
    (True, True, False, False, 1),
    (True, False, True, False, 0),
    (False, True, False, True, 0),
    (False, True, True, False, 1),
    (True, False, False, True, 1)
])
def test_physical_environment_limit_method_detect_spoofing_attack(is_on_water, is_on_land, on_water, on_land,
                                                                  expected_spoofing_indicator):
    handler = HandlerDummy()
    state_history = StateHistory()
    latest_state = NmeaState(update_time=datetime(2018, 1, 1, 0, 0, 0), latitude=0, longitude=0)
    state_history.add_state(latest_state)
    method = PhysicalEnvironmentLimitMethodTestable(handler, on_land=on_land,
                                                    on_water=on_water)
    method.water_map.static_is_on_water = is_on_water
    method.water_map.static_is_on_land = is_on_land
    spoofing_indicator = method.detect_spoofing_attack(device_id='DEVICE1', latest_state=latest_state,
                                                       previous_state=None, state_history=state_history)
    assert spoofing_indicator == expected_spoofing_indicator


class TwoLineElementDummy:

    def __init__(self, pseudo_random_noise, elevation, azimuth):
        self.pseudo_random_noise = pseudo_random_noise
        self.elevation = elevation
        self.azimuth = azimuth

    def observer_view(self, *_args, **_kwargs):
        return self.elevation, self.azimuth


class OrbitPositionsMethodTestable(OrbitPositionsMethod):

    def load_two_line_elements(self):
        self.two_line_elements = []
        for i in range(4):
            self.two_line_elements.append(TwoLineElementDummy(i, i, i))


@pytest.mark.parametrize('satellite_data, expected_spoofing_indicator', [
    ([(0, 0, 0), (1, 1, 1), (2, 2, 2), (3, 3, 3)], 0.25),
    ([(0, 0, 0), (1, 5, 1), (2, 2, 5), (3, 3, 3)], 0.75),
    ([(0, 0, 0), (1, 1.5, 1), (2, 1.5, 2.5), (3, 3.2, 3)], 0.25),
    ([(0, 0, 2), (1, 12, 1), (2, 5, 1), (3, 5, 6)], 1)
])
def test_orbit_positions_method_detect_spoofing_attack(satellite_data, expected_spoofing_indicator):
    handler = HandlerDummy()
    state_history = StateHistory()
    satellite_states = create_orbit_positions_method_satellite_dummy_states(satellite_data)
    latest_state = NmeaState(update_time=datetime(2018, 1, 1, 0, 0, 0), gps_time=datetime(2018, 1, 1, 0, 0, 0),
                             latitude=0, longitude=0, height_above_sea_level=0, satellites=satellite_states)
    state_history.add_state(latest_state)
    method = OrbitPositionsMethodTestable(handler, min_elevation=1, allowed_azimuth_deviation=1,
                                          allowed_elevation_deviation=1)
    spoofing_indicator = method.detect_spoofing_attack(device_id='DEVICE1', latest_state=latest_state,
                                                       previous_state=None, state_history=state_history)
    assert spoofing_indicator == expected_spoofing_indicator


def create_orbit_positions_method_satellite_dummy_states(satellite_data):
    satellites = []
    for pseudo_random_noise, elevation, azimuth in satellite_data:
        state_dummy = SatelliteState(pseudo_random_noise=pseudo_random_noise, elevation=elevation, azimuth=azimuth,
                                     is_visible=True)
        satellites.append(state_dummy)
    return satellites


@pytest.mark.parametrize('local_time_drift,expected_spoofing_indicator', [
    (0.0, 0), (0.49, 0), (1.0, 1), (10.0, 1)
])
def test_time_drift_method_detect_spoofing_attack(local_time_drift, expected_spoofing_indicator):
    handler = HandlerDummy()
    state_history = StateHistory()
    method = TimeDriftMethod(handler, max_clock_drift_dev=0.5)
    spoofing_indicator = None
    for i in range(20):
        time = i
        local_time = i + (local_time_drift if i == 20 - 1 else 0)
        gps_time = datetime(2018, 1, 1, 0, 0, int(time), int((time - int(time)) * 100000))
        update_time = datetime(2018, 1, 1, 0, 0, int(local_time), int((local_time - int(local_time)) * 100000))
        latest_state = NmeaState(update_time=update_time, gps_time=gps_time)
        state_history.add_state(latest_state)
        spoofing_indicator = method.detect_spoofing_attack(device_id='DEVICE1', latest_state=latest_state,
                                                           previous_state=None, state_history=state_history)
    assert spoofing_indicator == expected_spoofing_indicator


@pytest.mark.parametrize('satellite_data,expected_spoofing_indicator', [
    ([40, 41, 42, 50], 0),
    ([39, 41, 42, 50], 0.25),
    ([39, 10, 55, 51], 1)
])
def test_carrier_to_noise_method_detect_spoofing_attack(satellite_data, expected_spoofing_indicator):
    handler = HandlerDummy()
    state_history = StateHistory()
    satellite_states = create_carrier_to_noise_method_satellite_dummy_states(satellite_data)
    state_dummy = NmeaState(update_time=datetime(2018, 1, 1, 0, 0, 0), satellites=satellite_states)
    state_history.add_state(state_dummy)
    method = CarrierToNoiseDensityMethod(handler, min_carrier_to_noise_density=40, max_carrier_to_noise_density=50)
    spoofing_indicator = method.detect_spoofing_attack(device_id='DEVICE1', latest_state=state_dummy,
                                                       previous_state=None, state_history=state_history)
    assert spoofing_indicator == expected_spoofing_indicator


def create_carrier_to_noise_method_satellite_dummy_states(satellite_data):
    satellites = []
    for carrier_to_noise_density in satellite_data:
        state_dummy = SatelliteState(carrier_to_noise_density=carrier_to_noise_density, is_visible=True)
        satellites.append(state_dummy)
    return satellites
