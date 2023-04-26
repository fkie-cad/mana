import os

from PIL import Image


class WaterMap:

    def __init__(self):
        self.map_image = self.get_image_resource()
        self.width, self.height = self.map_image.size

    def is_on_land(self, latitude, longitude, threshold=0.25):
        return not self.is_on_water(latitude, longitude, threshold=1 - threshold)

    def is_on_water(self, latitude, longitude, threshold=0.25):
        water_probability = self.water_probability(latitude, longitude)
        return water_probability > threshold

    def water_probability(self, latitude, longitude):
        pixel_position = self.latitude_longitude_to_pixel_position(latitude, longitude)
        rgba = self.map_image.getpixel(pixel_position)
        grayscale = self.rgb_to_grayscale(rgba)
        water_probability = 1 - grayscale / 255
        return water_probability

    def latitude_longitude_to_pixel_position(self, latitude, longitude):
        x = self.width * (180 + longitude) / 360
        y = self.height * (90 - latitude) / 180
        return int(x) % self.width, int(y) % self.height

    @staticmethod
    def get_image_resource():
        water_map_file = os.path.dirname(os.path.abspath(__file__)) + "/water_map.png"
        return Image.open(water_map_file)

    @staticmethod
    def rgb_to_grayscale(rgba):
        r, g, b, _ = rgba
        grayscale = ((r + g + b) / 3)
        return grayscale
