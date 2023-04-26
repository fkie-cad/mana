import datetime as dt

from mana.state import SatelliteState, NmeaState


class NmeaParser:

    @classmethod
    def parse(cls, state: NmeaState, update_time, sentence):
        data_bytes = sentence.encode()
        if not cls.is_nmea_sentence(data_bytes):
            error_message = "The given sentence '{}' is not a valid nmea sentence!"
            raise InvalidNmeaSentenceException(error_message.format(sentence))
        data_bytes, checksum_bytes = data_bytes[1:].split(b'*')
        checksum = int(checksum_bytes.decode(), 16)
        if not cls.is_nmea_checksum_valid(data_bytes, checksum):
            error_message = "The checksum of the given nmea sentence '{}' is not correct!"
            raise InvalidNmeaSentenceException(error_message.format(sentence))
        data_fields = data_bytes.split(b',')
        descriptor = data_fields.pop(0).decode()
        device_descriptor = descriptor[:2]
        packet_descriptor = descriptor[2:]
        parse_function_name = "parse_{}_{}".format(device_descriptor, packet_descriptor).lower()
        try:
            parse_function = getattr(cls, parse_function_name)
        except AttributeError as e:
            error_message = "The nmea sentence of the type '{}' is not supported!"
            raise NmeaSentenceNotSupportedException(error_message.format(descriptor))
        state.last_nmea_sentence = sentence
        state.update_time = update_time
        state = parse_function(state, data_fields)
        return state

    @classmethod
    def parse_gp_gsv(cls, state: NmeaState, data_fields):
        message_number = cls.parse_int(data_fields[1])
        satellite_count = cls.parse_int(data_fields[2])
        if message_number == 1:
            if state.satellites is not None:
                for satellite in state.satellites:
                    satellite.is_visible = False
        satellites_in_message = 4
        if message_number * 4 > satellite_count:
            satellites_in_message = satellite_count % 4
        for i in range(satellites_in_message):
            pseudo_random_noise = cls.parse_int(data_fields[3 + i * 4])
            elevation = cls.parse_int(data_fields[4 + i * 4])
            azimuth = cls.parse_int(data_fields[5 + i * 4])
            carrier_to_noise_density = cls.parse_int(data_fields[6 + i * 4])
            matching_satellites = [s for s in state.satellites if s.pseudo_random_noise == pseudo_random_noise]
            satellite = SatelliteState() if len(matching_satellites) == 0 else matching_satellites[0]
            if satellite.pseudo_random_noise is None:
                satellite.pseudo_random_noise = pseudo_random_noise
                satellite.is_active = False
                state.satellites.append(satellite)
            satellite.elevation = elevation
            satellite.azimuth = azimuth
            satellite.carrier_to_noise_density = carrier_to_noise_density
            satellite.is_visible = True
        return state

    @classmethod
    def parse_gp_rmc(cls, state: NmeaState, data_fields):
        if data_fields[1] != b'A':
            return None
        latitude_data_bytes = data_fields[2]
        latitude_dir_bytes = data_fields[3]
        longitude_data_bytes = data_fields[4]
        longitude_dir_bytes = data_fields[5]
        latitude, longitude = cls.parse_latitude_longitude(latitude_data_bytes, latitude_dir_bytes,
                                                           longitude_data_bytes, longitude_dir_bytes)
        speed = cls.parse_float(data_fields[6])
        course = cls.parse_float(data_fields[7])
        time = cls.parse_time(time_bytes=data_fields[0], date_bytes=data_fields[8])
        magnetic_declination_bytes = data_fields[9]
        magnetic_dir_bytes = data_fields[10]
        magnetic_declination = cls.parse_magnetic_declination(magnetic_declination_bytes, magnetic_dir_bytes)
        state.gps_time = time
        state.latitude = latitude
        state.longitude = longitude
        state.speed = speed
        state.course = course
        state.magnetic_declination = magnetic_declination
        return state

    @classmethod
    def parse_gp_gsa(cls, state: NmeaState, data_fields):
        if state.satellites is not None:
            for satellite in state.satellites:
                satellite.is_active = False
        for i in range(12):
            pseudo_random_noise = cls.parse_int(data_fields[2 + i])
            if pseudo_random_noise is None:
                continue
            matching_satellites = [s for s in state.satellites if s.pseudo_random_noise == pseudo_random_noise]
            satellite = SatelliteState() if len(matching_satellites) == 0 else matching_satellites[0]
            if satellite.pseudo_random_noise is None:
                satellite.pseudo_random_noise = pseudo_random_noise
                state.satellites.append(satellite)
            satellite.is_active = True
        positional_dilution_of_precision = cls.parse_float(data_fields[14])
        horizontal_dilution_of_precision = cls.parse_float(data_fields[15])
        vertical_dilution_of_precision = cls.parse_float(data_fields[16])
        state.positional_dilution_of_precision = positional_dilution_of_precision
        state.horizontal_dilution_of_precision = horizontal_dilution_of_precision
        state.vertical_dilution_of_precision = vertical_dilution_of_precision
        return state

    @classmethod
    def parse_gp_gga(cls, state: NmeaState, data_fields):
        latitude_data_bytes = data_fields[1]
        latitude_dir_bytes = data_fields[2]
        longitude_data_bytes = data_fields[3]
        longitude_dir_bytes = data_fields[4]
        latitude, longitude = cls.parse_latitude_longitude(latitude_data_bytes, latitude_dir_bytes,
                                                           longitude_data_bytes, longitude_dir_bytes)
        gps_quality = cls.parse_int(data_fields[5])
        horizontal_dilution_of_precision = cls.parse_float(data_fields[7])
        height_above_sea_level = cls.parse_float(data_fields[8])
        geoidal_separation = cls.parse_float(data_fields[10])
        state.latitude = latitude
        state.longitude = longitude
        state.gps_quality = gps_quality
        state.horizontal_dilution_of_precision = horizontal_dilution_of_precision
        state.height_above_sea_level = height_above_sea_level
        state.geoidal_separation = geoidal_separation
        return state

    @classmethod
    def parse_gp_gll(cls, state: NmeaState, data_fields):
        if data_fields[5] != b'A':
            return None

        latitude_data_bytes = data_fields[0]
        latitude_dir_bytes = data_fields[1]
        longitude_data_bytes = data_fields[2]
        longitude_dir_bytes = data_fields[3]
        latitude, longitude = cls.parse_latitude_longitude(latitude_data_bytes, latitude_dir_bytes,
                                                           longitude_data_bytes, longitude_dir_bytes)
        state.latitude = latitude
        state.longitude = longitude
        return state

    @classmethod
    def parse_gp_vtg(cls, state: NmeaState, data_fields):
        course = cls.parse_float(data_fields[0])
        speed = cls.parse_float(data_fields[4])
        state.course = course
        state.speed = speed
        return state

    @classmethod
    def parse_latitude_longitude(cls, latitude_data_bytes, latitude_dir_bytes, longitude_data_bytes,
                                 longitude_dir_bytes):
        latitude = None
        longitude = None
        if cls.is_byte_string_valid(latitude_data_bytes, latitude_dir_bytes, longitude_data_bytes,
                                    longitude_dir_bytes):
            latitude_dir = (1 if latitude_dir_bytes == b'N' else -1)
            latitude = latitude_dir * (int(latitude_data_bytes[:2]) + float(latitude_data_bytes[2:]) / 60)
            longitude_dir = (1 if longitude_dir_bytes == b'E' else -1)
            longitude = longitude_dir * (int(longitude_data_bytes[:3]) + float(longitude_data_bytes[3:]) / 60)
        return latitude, longitude

    @classmethod
    def parse_float(cls, data_bytes):
        if not cls.is_byte_string_valid(data_bytes):
            return None
        return float(data_bytes)

    @classmethod
    def parse_int(cls, data_bytes):
        if not cls.is_byte_string_valid(data_bytes):
            return None
        return int(data_bytes)

    @classmethod
    def parse_time(cls, time_bytes, date_bytes):
        time = None
        if cls.is_byte_string_valid(time_bytes, date_bytes):
            time_string = (date_bytes + time_bytes).decode()
            time = dt.datetime.strptime(time_string, '%d%m%y%H%M%S.%f')
        return time

    @classmethod
    def parse_magnetic_declination(cls, magnetic_declination_bytes, magnetic_dir_bytes):
        magnetic_declination = None
        if cls.is_byte_string_valid(magnetic_declination_bytes, magnetic_dir_bytes):
            magnetic_dir = (1 if magnetic_dir_bytes == b'E' else -1)
            magnetic_declination = magnetic_dir * float(magnetic_declination_bytes)
        return magnetic_declination

    @staticmethod
    def is_nmea_sentence(data_bytes):
        return data_bytes[0] == b'$'[0] and data_bytes[-3] == b'*'[0]

    @staticmethod
    def is_nmea_checksum_valid(data_bytes, checksum):
        calculated_checksum = 0
        for b in data_bytes:
            calculated_checksum ^= b

        return checksum == calculated_checksum

    @staticmethod
    def is_byte_string_valid(*args):
        for arg in args:
            if arg is None or len(arg) == 0:
                return False
        return True


class InvalidNmeaSentenceException(Exception):
    pass


class NmeaSentenceNotSupportedException(Exception):
    pass
