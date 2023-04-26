from unittest import mock

from mana.method.water_map import WaterMap


class ImageDummy:

    def __init__(self):
        self.size = 10, 10

    @staticmethod
    def getpixel(position):
        if position == (0, 0):
            return 4 * (0,)
        return 4 * (255,)


@mock.patch("mana.method.water_map.WaterMap.get_image_resource")
def test_water_map_is_on_water_land(get_image_resource_mock):
    get_image_resource_mock.return_value = ImageDummy()
    water_map = WaterMap()
    assert water_map.is_on_water(-90, -180) is True
    assert water_map.is_on_land(-90, -180) is False
    assert water_map.is_on_water(0, 0) is False
    assert water_map.is_on_land(0, 0) is True
    assert water_map.is_on_water(45, 90) is False
    assert water_map.is_on_land(45, 90) is True
