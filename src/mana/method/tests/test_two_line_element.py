from datetime import datetime
from unittest import mock

import pytest

from mana.method.two_line_element import TwoLineElement, actual_satellite_constellation_two_line_elements

two_line_element_set = [
    "18",
    "1 22877C 93068A   18268.70201389 -.00000000  00000-0  00000-0 0  2687",
    "2 22877  54.4972  79.3811 0147546  77.1415 180.3797  2.00568932    11",
    "13",
    "1 24876C 97035A   18268.70201389  .00000000  00000-0  00000-0 0  2685",
    "2 24876  55.4780 208.8266 0031882  83.0567 250.3308  2.00564522    19"]


@mock.patch("mana.method.two_line_element.read_lines_of_resource")
def test_actual_satellite_constellation_two_line_elements(read_lines_of_resource_mock):
    read_lines_of_resource_mock.return_value = two_line_element_set
    satellite_constellation = actual_satellite_constellation_two_line_elements()
    assert len(satellite_constellation) == 2


def test_two_line_element_observer_view():
    two_line_element = TwoLineElement(*two_line_element_set[:3])
    elevation, azimuth = two_line_element.observer_view(datetime(2018, 1, 1, 0, 0, 0), 0, 0, 0)
    assert elevation == pytest.approx(-12.81443)
    assert azimuth == pytest.approx(216.06389)
