import math
import os

import ephem


def actual_satellite_constellation_two_line_elements():
    satellite_constellation_generator = actual_satellite_constellation_two_line_element_generator()
    two_line_elements = list(satellite_constellation_generator)
    return two_line_elements


def actual_satellite_constellation_two_line_element_generator():
    i = 0
    lines = read_lines_of_resource()
    while i < len(lines):
        pseudo_random_noise, line1, line2 = lines[i], lines[i + 1], lines[i + 2]
        two_line_element = TwoLineElement(int(pseudo_random_noise), line1, line2)
        yield two_line_element
        i += 3


def read_lines_of_resource():
    tle_file = os.path.dirname(os.path.abspath(__file__)) + "/gps.tle"
    with open(tle_file, 'r') as file:
        lines = list(file)
    return lines


class TwoLineElement:

    def __init__(self, pseudo_random_noise, line1, line2):
        self.pseudo_random_noise = pseudo_random_noise
        self.orbit = ephem.readtle(str(pseudo_random_noise), line1, line2)
        self.observer = ephem.Observer()

    def observer_view(self, time, latitude, longitude, height):
        self.observer.date = time
        self.observer.lat = str(latitude)
        self.observer.lon = str(longitude)
        self.observer.elev = height
        self.orbit.compute(self.observer)
        elevation_radians = float(self.orbit.alt)
        elevation = math.degrees(elevation_radians)
        azimuth_radians = float(self.orbit.az)
        azimuth = math.degrees(azimuth_radians)
        return elevation, azimuth
