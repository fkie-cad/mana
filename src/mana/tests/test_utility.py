from datetime import datetime
from collections import namedtuple

import pytest

from mana.utility import string_to_datetime, minimum_angle_difference


@pytest.fixture
def test_named_tuple_factory():
    TestNamedTuple = namedtuple("TestNamedTuple", ["value1", "value2", "value3"])
    return TestNamedTuple


@pytest.mark.parametrize("datetime_string,expected_datetime", [
    ("2018-10-15 21:49:50.1", datetime(2018, 10, 15, 21, 49, 50, 100000))
])
def test_string_to_datetime(datetime_string, expected_datetime):
    datetime_object = string_to_datetime(datetime_string)
    assert datetime_object == expected_datetime


@pytest.mark.parametrize("angle1,angle2,expected_angle_difference", [
    (10, 350, 20),
    (170, 190, 20),
    (370, 380, 10),
    (10, 405, 35)
])
def test_minimum_angle_difference(angle1, angle2, expected_angle_difference):
    angle_difference = minimum_angle_difference(angle1, angle2)
    assert angle_difference == pytest.approx(expected_angle_difference)
