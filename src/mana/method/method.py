import math
from copy import deepcopy

import numpy as np
from sklearn import linear_model

from mana.method.two_line_element import actual_satellite_constellation_two_line_elements
from mana.method.water_map import WaterMap
from mana.utility import minimum_angle_difference, is_state_sufficiently_defined


def find_min_max_in_list(measurements):
    min_measurement = float('inf')
    max_measurement = -float('inf')
    for measurement in measurements:
        min_measurement = min(measurement, min_measurement)
        max_measurement = max(measurement, max_measurement)
    return min_measurement, max_measurement


class Method:
    debug = False

    def __init__(self, handler, *args, **kwargs):
        super().__init__()
        self.handler = handler
        self.required_state_fields = []
        self.variable_state_fields = []
        self.required_satellite_state_fields = []
        self.min_sufficient_satellite_state_count = 0

    def spoofing_indicator(self, device_id, latest_state, previous_state, state_history):
        return self.detect_spoofing_attack(device_id, latest_state, previous_state, state_history)

    def detect_spoofing_attack(self, device_id, latest_state, previous_state, state_history):
        raise NotImplementedError()

    def _print_debug_message(self, *args):
        if self.debug:
            print(*args)


class AverageMethod(Method):

    def __init__(self, handler, max_previous_spoofing_indicators_count=100, *args, **kwargs):
        super().__init__(handler=handler, *args, **kwargs)
        self.max_previous_spoofing_indicators_count = max_previous_spoofing_indicators_count
        self.previous_spoofing_indicators = [0] * self.max_previous_spoofing_indicators_count

    def spoofing_indicator(self, device_id, latest_state, previous_state, state_history):
        spoofing_indicator = super().spoofing_indicator(device_id, latest_state, previous_state, state_history)
        self.add_spoofing_indicator(spoofing_indicator)
        average_spoofing_indicator = self.calculate_average_spoofing_indicator()
        return average_spoofing_indicator

    def add_spoofing_indicator(self, spoofing_attack_probability):
        self.previous_spoofing_indicators.insert(0, spoofing_attack_probability)
        self.previous_spoofing_indicators = \
            self.previous_spoofing_indicators[:self.max_previous_spoofing_indicators_count]

    def calculate_average_spoofing_indicator(self):
        previous_spoofing_indicators_length = len(self.previous_spoofing_indicators)
        previous_spoofing_indicators_sum = sum(self.previous_spoofing_indicators)
        average_spoofing_indicator = previous_spoofing_indicators_sum / previous_spoofing_indicators_length
        return average_spoofing_indicator

    def detect_spoofing_attack(self, device_id, latest_state, previous_state, state_history):
        raise NotImplementedError()


class GroupMethod(Method):

    def __init__(self, handler, method_classes, method_options=None, *args, **kwargs):
        super().__init__(handler=handler, *args, **kwargs)
        self.methods = []
        self.setup_methods(method_classes, method_options)

    def spoofing_indicator(self, device_id, latest_state, previous_state, state_history):
        raise NotImplementedError()

    def detect_spoofing_attack(self, device_id, latest_state, previous_state, state_history):
        pass

    def setup_methods(self, method_classes, method_options):
        if method_options is None:
            method_options = [{} for _ in range(len(method_classes))]
        for method_class, method_option in zip(method_classes, method_options):
            method = method_class(self.handler, **method_option)
            self.add_method(method)

    def add_method(self, method):
        self.required_state_fields.extend(method.required_state_fields)
        self.variable_state_fields.extend(method.variable_state_fields)
        self.required_satellite_state_fields.extend(method.required_satellite_state_fields)
        self.min_sufficient_satellite_state_count = max(self.min_sufficient_satellite_state_count,
                                                        method.min_sufficient_satellite_state_count)
        self.methods.append(method)


class OrGroupMethod(GroupMethod):

    def spoofing_indicator(self, device_id, latest_state, previous_state, state_history):
        return max(method.spoofing_indicator(device_id, latest_state, previous_state, state_history) for method in
                   self.methods)


class AndGroupMethod(GroupMethod):

    def spoofing_indicator(self, device_id, latest_state, previous_state, state_history):
        return min(method.spoofing_indicator(device_id, latest_state, previous_state, state_history) for method in
                   self.methods)


class AverageGroupMethod(GroupMethod):

    def spoofing_indicator(self, device_id, latest_state, previous_state, state_history):
        spoofing_indicators = [method.spoofing_indicator(device_id, latest_state, previous_state, state_history) for
                               method in self.methods]
        return sum(spoofing_indicators) / len(spoofing_indicators)


class WeightedAverageGroupMethod(GroupMethod):

    def __init__(self, handler, method_classes, method_options, method_weights, *args, **kwargs):
        super().__init__(handler=handler, method_classes=method_classes, method_options=method_options, *args, **kwargs)
        self.method_weights = method_weights
        assert len(method_weights) == len(method_weights)
        assert sum(method_weights) == 1

    def spoofing_indicator(self, device_id, latest_state, previous_state, state_history):
        spoofing_indicators = [method.spoofing_indicator(device_id, latest_state, previous_state, state_history) for
                               method in self.methods]
        weighted_spoofing_indicators = [self.method_weights[i] * a for i, a in enumerate(spoofing_indicators)]
        return sum(weighted_spoofing_indicators)


class MultipleReceiversMethod(Method):  # PDM
    calibration = False

    def __init__(self, handler, distances, distance_ratio_thresholds, new_measurement_weight=0.1, *args, **kwargs):
        super().__init__(handler=handler, *args, **kwargs)
        self.distances = distances
        self.distance_ratio_thresholds = distance_ratio_thresholds
        self.new_measurement_weight = new_measurement_weight
        if self.calibration:
            self.measurements = {}

        self.past_measurements = {}
        self.required_state_fields.extend(["gps_time", "update_time", "latitude", "longitude"])
        self.variable_state_fields.extend(["gps_time", "latitude", "longitude"])

    def detect_spoofing_attack(self, device_id, latest_state, previous_state, state_history):
        for device_ids, expected_distance in self.distances.items():
            if device_id not in device_ids:
                continue
            device_id_a, device_id_b = device_ids
            other_device_id = device_id_a
            if device_id_a == device_id:
                other_device_id = device_id_b
            other_device = self.handler.device(other_device_id)
            if other_device is None:
                continue
            other_state_history = other_device.state_history
            other_latest_state = other_state_history.state(0)
            if not is_state_sufficiently_defined(other_latest_state, self.required_state_fields):
                continue
            target_state_history, reference_state = min(
                (other_state_history, latest_state), (state_history, other_latest_state),
                key=lambda x: x[1].update_time)
            reference_time = reference_state.update_time
            estimated_state = self.estimate_state(target_state_history, reference_time)
            if not is_state_sufficiently_defined(estimated_state, self.required_state_fields):
                continue
            measured_distance = self.positional_distance_between_states(reference_state, estimated_state)

            if device_ids not in self.past_measurements:
                self.past_measurements[device_ids] = []
                self.past_measurements[device_ids] = expected_distance

            self.past_measurements[device_ids] = (1 - self.new_measurement_weight) * self.past_measurements[
                device_ids] + self.new_measurement_weight * measured_distance

            average_distance = self.past_measurements[device_ids]
            if self.calibration:
                if device_ids not in self.measurements:
                    self.measurements[device_ids] = []
                self.measurements[device_ids].append(average_distance)

            distance_ratio = average_distance / expected_distance
            if distance_ratio < self.distance_ratio_thresholds[device_ids]:
                return 1
        return 0

    def estimate_state(self, state_history, reference_time):
        state_after_reference_time = state_history.state_after(reference_time)
        state_before_reference_time = state_history.state_before(reference_time)
        if not is_state_sufficiently_defined(state_after_reference_time, self.required_state_fields) \
                or not is_state_sufficiently_defined(state_before_reference_time, self.required_state_fields):
            return None
        old_delta = (state_after_reference_time.update_time - state_before_reference_time.update_time).total_seconds()
        new_delta = (reference_time - state_before_reference_time.update_time).total_seconds()
        delta = new_delta / old_delta if old_delta != 0 else 0
        latitude_difference = state_after_reference_time.latitude - state_before_reference_time.latitude
        longitude_difference = state_after_reference_time.longitude - state_before_reference_time.longitude
        new_latitude = state_before_reference_time.latitude + latitude_difference * delta
        new_longitude = state_before_reference_time.longitude + longitude_difference * delta
        estimated_state = deepcopy(state_before_reference_time)
        estimated_state.update_time = reference_time
        estimated_state.latitude = new_latitude
        estimated_state.longitude = new_longitude
        return estimated_state

    def calculate_parameters(self):
        parameters = {
            "distances": self.distances,
            "distance_ratio_thresholds": {},
        }

        for device_ids, device_measurements in self.measurements.items():
            actual_distance = self.distances[device_ids]
            min_measurement, max_measurement = find_min_max_in_list(self.measurements[device_ids])
            parameters['distance_ratio_thresholds'][device_ids] = min_measurement / actual_distance

        return parameters

    @staticmethod
    def positional_distance_between_states(state1, state2):
        latitude1 = math.radians(state1.latitude)
        latitude2 = math.radians(state2.latitude)
        dlon = math.radians(state2.longitude) - math.radians(state1.longitude)
        dlat = latitude2 - latitude1
        a = math.sin(dlat / 2) ** 2 + math.cos(latitude1) * math.cos(latitude2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = 6378100 * c
        return distance


class PhysicalSpeedLimitMethod(Method):  # PCCspeed
    calibration = False

    def __init__(self, handler, max_speed, *args, **kwargs):
        super().__init__(handler=handler, *args, **kwargs)
        self.max_speed = max_speed
        self.required_state_fields.extend(["update_time", "speed"])
        self.variable_state_fields.extend(["update_time", "speed"])
        if self.calibration:
            self.measurements = []

    def detect_spoofing_attack(self, device_id, latest_state, previous_state, state_history):
        speed = latest_state.speed
        if self.calibration:
            self.measurements.append(speed)
            self._print_debug_message(latest_state.update_time, "PhysicalSpeedLimitMethod", speed)
        if speed > self.max_speed:
            self._print_debug_message(latest_state.update_time, "PhysicalSpeedLimitMethod", "DETECTED")
            return 1
        return 0

    def calculate_parameters(self):
        parameters = {
            "max_speed": 0
        }
        _, max_measurement = find_min_max_in_list(self.measurements)
        parameters["max_speed"] = max_measurement
        return parameters


class PhysicalRateOfTurnLimitMethod(Method):  # PCCrate_of_turn
    calibration = False

    def __init__(self, handler, max_rate_of_turn, min_speed_to_determine_rate_of_turn, *args, **kwargs):
        super().__init__(handler=handler, *args, **kwargs)
        self.max_rate_of_turn = max_rate_of_turn
        self.min_speed_to_determine_rate_of_turn = min_speed_to_determine_rate_of_turn
        self.required_state_fields.extend(["update_time", "course", "speed"])
        self.variable_state_fields.extend(["update_time"])

        self.signals = {}
        self.filteredY = {}
        self.avgFilter = {}
        self.stdFilter = {}
        self.lag = 10
        self.threshold = 50
        self.influence = 0.05

        if self.calibration:
            self.measurements = []

    def detect_spoofing_attack(self, device_id, latest_state, previous_state, state_history):
        speed = latest_state.speed
        if speed < self.min_speed_to_determine_rate_of_turn:
            return 0
        delta = (latest_state.update_time - previous_state.update_time).total_seconds()
        course_difference = minimum_angle_difference(latest_state.course, previous_state.course)
        rate_of_turn = abs(course_difference / delta)

        self._print_debug_message(latest_state.update_time, "PhysicalRateOfTurnLimitMethod", rate_of_turn)
        if self.calibration:
            self.measurements.append(rate_of_turn)

        if rate_of_turn > self.max_rate_of_turn:
            self._print_debug_message(latest_state.update_time, "PhysicalRateOfTurnLimitMethod", "DETECTED")
            return 1
        return 0

    def calculate_parameters(self):
        parameters = {
            "max_rate_of_turn": 0
        }
        _, max_measurement = find_min_max_in_list(self.measurements)
        parameters["max_rate_of_turn"] = max_measurement
        return parameters


class PhysicalHeightLimitMethod(Method):  # PCCheight
    calibration = False

    def __init__(self, handler, min_height, max_height, *args, **kwargs):
        super().__init__(handler=handler, *args, **kwargs)
        self.min_height = min_height
        self.max_height = max_height
        self.required_state_fields.extend(["height_above_sea_level"])
        self.variable_state_fields.extend(["height_above_sea_level"])
        if self.calibration:
            self.measurements = []

    def detect_spoofing_attack(self, device_id, latest_state, previous_state, state_history):
        height = latest_state.height_above_sea_level
        if self.calibration:
            self.measurements.append(height)
        self._print_debug_message(latest_state.update_time, "PhysicalHeightLimitMethod", height)
        if not self.min_height <= height <= self.max_height:
            self._print_debug_message(latest_state.update_time, "PhysicalHeightLimitMethod", "DETECTED")
            return 1
        return 0

    def calculate_parameters(self):
        parameters = {
            "min_height": 0,
            "max_height": 0,
        }
        min_measurement, max_measurement = find_min_max_in_list(self.measurements)
        parameters["min_height"] = min_measurement
        parameters["max_height"] = max_measurement
        return parameters


class PhysicalEnvironmentLimitMethod(Method):  # PCCenvironment
    calibration = False

    def __init__(self, handler, on_land, on_water, *args, **kwargs):
        super().__init__(handler=handler, *args, **kwargs)
        self.on_land = on_land
        self.on_water = on_water
        self.water_map = None
        self.required_state_fields.extend(["latitude", "longitude"])
        self.variable_state_fields.extend(["latitude", "longitude"])
        self.load_world_map()
        if self.calibration:
            self.measurements_on_land = []
            self.measurements_on_water = []

    def detect_spoofing_attack(self, device_id, latest_state, previous_state, state_history):
        if self.on_water and self.on_land and not self.calibration:
            return 0
        elif not (self.on_water or self.on_land) and not self.calibration:
            return 1
        latitude, longitude = latest_state.latitude, latest_state.longitude
        is_on_water = self.water_map.is_on_water(latitude, longitude)
        is_on_land = self.water_map.is_on_land(latitude, longitude)
        if self.calibration:
            self.measurements_on_land.append(is_on_land)
            self.measurements_on_water.append(is_on_water)
        if (self.on_water and not is_on_water) \
                or (self.on_land and not is_on_land):
            return 1
        return 0

    def load_world_map(self):
        self.water_map = WaterMap()

    def calculate_parameters(self):
        parameters = {
            "on_land": any(self.measurements_on_land),
            "on_water": any(self.measurements_on_water),
        }
        return parameters


class OrbitPositionsMethod(Method):
    calibration = False

    def __init__(self, handler, min_elevation, allowed_azimuth_deviation, allowed_elevation_deviation, *args,
                 **kwargs):
        super().__init__(handler=handler, *args, **kwargs)
        self.two_line_elements = None
        self.min_elevation = min_elevation
        self.allowed_azimuth_deviation = allowed_azimuth_deviation
        self.allowed_elevation_deviation = allowed_elevation_deviation
        self.required_state_fields.extend(
            ["update_time", "latitude", "longitude", "height_above_sea_level", "satellites"])
        self.variable_state_fields.extend(["satellites"])
        self.required_satellite_state_fields.extend(["pseudo_random_noise", "is_visible", "azimuth", "elevation"])
        self.min_sufficient_satellite_state_count = 1
        self.load_two_line_elements()

    def detect_spoofing_attack(self, device_id, latest_state, previous_state, state_history):
        spoofing_score = 0
        counter = 0
        for satellite_state in latest_state.satellites:
            if not is_state_sufficiently_defined(satellite_state, self.required_satellite_state_fields):
                continue
            if not satellite_state.is_visible:
                continue
            two_line_element = self.two_line_element(satellite_state.pseudo_random_noise)
            if two_line_element is None:
                continue
            elevation, azimuth = two_line_element.observer_view(latest_state.update_time, latest_state.latitude,
                                                                latest_state.longitude,
                                                                latest_state.height_above_sea_level)
            azimuth_diff = minimum_angle_difference(azimuth, satellite_state.azimuth)
            elevation_diff = minimum_angle_difference(elevation, satellite_state.elevation)
            if satellite_state.elevation < self.min_elevation or \
                    azimuth_diff > self.allowed_azimuth_deviation or \
                    elevation_diff > self.allowed_elevation_deviation:
                spoofing_score += 1
            counter += 1
        spoofing_indicator = spoofing_score / counter if counter > 0 else 0
        return spoofing_indicator

    def two_line_element(self, pseudo_random_noise):
        for two_line_element in self.two_line_elements:
            if two_line_element.pseudo_random_noise == pseudo_random_noise:
                return two_line_element
        return None

    def load_two_line_elements(self):
        self.two_line_elements = actual_satellite_constellation_two_line_elements()

    @staticmethod
    def is_satellite_state_sufficiently_defined(state):
        return state is not None and all(
            a is not None for a in [state.pseudo_random_noise, state.elevation, state.azimuth, state.is_visible])

    def calculate_parameters(self):
        return {}


class TimeDriftMethod(Method):
    calibration = False

    def __init__(self, handler, max_clock_drift_dev, *args, **kwargs):
        super().__init__(handler=handler, *args, **kwargs)
        self.max_clock_drift_dev = max_clock_drift_dev
        self.required_state_fields.extend(["update_time", "gps_time"])
        self.variable_state_fields.extend(["gps_time"])
        self.base_line = {}
        self.past_measurements = {}
        if self.calibration:
            self.measurements = {}
        self.min_past_measurements = 10
        self.max_past_measurements = 60

    def detect_spoofing_attack(self, device_id, latest_state, previous_state, state_history):
        update_time = latest_state.update_time
        gps_time = latest_state.gps_time

        if device_id not in self.base_line:
            self.base_line[device_id] = update_time
            self.past_measurements[device_id] = []

        time_since_start = (update_time - self.base_line[device_id]).total_seconds()
        clock_drift = (gps_time - update_time).total_seconds()

        self.past_measurements[device_id].append((time_since_start, clock_drift))

        if self.calibration:
            if device_id not in self.measurements:
                self.measurements[device_id] = []
            self.measurements[device_id].append((time_since_start, clock_drift))

        if len(self.past_measurements[device_id]) < self.min_past_measurements:
            return 0

        X, y = zip(*self.past_measurements[device_id][:-1])
        X = np.array([X]).T
        y = np.array(y)
        y += np.random.normal(0.000001, 0.0001, y.shape)  # BUG: perfect horizontal lines throw a value error

        ransac = linear_model.RANSACRegressor()
        try:
            ransac.fit(X, y)
        except ValueError:
            return 0

        expected_clock_drift = ransac.predict(np.array([[time_since_start]]))[0]

        difference = expected_clock_drift - clock_drift
        self.past_measurements[device_id] = self.past_measurements[device_id][-self.max_past_measurements:]

        if difference > self.max_clock_drift_dev:
            return 1
        return 0

    def calculate_parameters(self):
        m, b = -float('inf'), -float('inf')
        for device_id in self.measurements.keys():
            x, y = zip(*self.measurements[device_id])
            result = np.polyfit(x, y, 1)
            m, b = max(m, abs(result[0])), max(b, abs(result[1]))
        parameters = {
            "start_clock_drift": b,
            "expected_clock_drift_per_second": m,
        }
        return parameters


class CarrierToNoiseDensityMethod(Method):

    def __init__(self, handler, min_carrier_to_noise_density, max_carrier_to_noise_density, *args,
                 **kwargs):
        super().__init__(handler=handler, *args, **kwargs)
        self.min_carrier_to_noise_density = min_carrier_to_noise_density
        self.max_carrier_to_noise_density = max_carrier_to_noise_density
        self.required_state_fields.extend(["satellites"])
        self.variable_state_fields.extend(["satellites"])
        self.required_satellite_state_fields.extend(["is_visible", "carrier_to_noise_density"])
        self.min_sufficient_satellite_state_count = 1

    def detect_spoofing_attack(self, device_id, latest_state, previous_state, state_history):
        spoofing_score = 0
        counter = 0
        for satellite_state in latest_state.satellites:
            if not is_state_sufficiently_defined(satellite_state, self.required_satellite_state_fields):
                continue
            if not satellite_state.is_visible:
                continue
            carrier_to_noise_density = satellite_state.carrier_to_noise_density
            self._print_debug_message(latest_state.update_time, "CarrierToNoiseDensityMethod", carrier_to_noise_density)
            if self.min_carrier_to_noise_density > carrier_to_noise_density \
                    or self.max_carrier_to_noise_density < carrier_to_noise_density:
                spoofing_score += 1
            counter += 1
        spoofing_indicator = spoofing_score / counter if counter > 0 else 0
        return spoofing_indicator

    @staticmethod
    def is_satellite_state_sufficiently_defined(state):
        return state is not None and all(a is not None for a in [state.carrier_to_noise_density, state.is_visible])
