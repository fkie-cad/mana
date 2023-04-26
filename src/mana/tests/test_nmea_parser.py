from datetime import datetime

import pytest

from mana.nmea_parser import NmeaParser, InvalidNmeaSentenceException, NmeaSentenceNotSupportedException
from mana.state import NmeaState

start_update_time = datetime(2018, 1, 1)


@pytest.mark.parametrize("sentence", ["ABC", "TEST,123*20", "$TEST,123"])
def test_nmea_parser_parse_invalid_sentence(sentence):
    state = NmeaState()
    nmea_parser = NmeaParser()
    with pytest.raises(InvalidNmeaSentenceException) as excinfo:
        nmea_parser.parse(state, start_update_time, sentence)
    error_message = str(excinfo.value)
    assert "The given sentence '" in error_message
    assert "' is not a valid nmea sentence!" in error_message


@pytest.mark.parametrize("sentence", ["$TEST*20", "$ABC*13"])
def test_nmea_parser_parse_invalid_checksum(sentence):
    state = NmeaState()
    nmea_parser = NmeaParser()
    with pytest.raises(InvalidNmeaSentenceException) as excinfo:
        nmea_parser.parse(state, start_update_time, sentence)
    error_message = str(excinfo.value)
    assert "The checksum of the given nmea sentence '" in error_message
    assert "' is not correct!" in error_message


@pytest.mark.parametrize("sentence", ["$TEST*16", "$ABC*40"])
def test_nmea_parser_parse_not_supported(sentence):
    state = NmeaState()
    nmea_parser = NmeaParser()
    with pytest.raises(NmeaSentenceNotSupportedException) as excinfo:
        nmea_parser.parse(state, start_update_time, sentence)
    error_message = str(excinfo.value)
    assert "The nmea sentence of the type '" in error_message
    assert "' is not supported!" in error_message


def test_nmea_parser_parse_gsv():
    state = NmeaState()
    nmea_parser = NmeaParser()
    sentences = [("$GPGSV,4,1,15,01,47,141,47,03,82,041,48,06,21,306,,09,23,209,35*78", 4),
                 ("$GPGSV,4,2,15,11,24,162,30,12,05,339,,14,16,045,11,17,42,266,41*70", 8),
                 ("$GPGSV,4,3,15,18,19,138,33,19,35,298,26,22,59,082,35,23,53,192,43*72", 12),
                 ("$GPGSV,4,4,15,25,00,018,,31,24,061,13,33,28,208,30*41", 15)]
    for sentence, expected_satellites_count in sentences:
        state = nmea_parser.parse(state, start_update_time, sentence)
        satellites_count = len(state.satellites)
        assert satellites_count == expected_satellites_count


def test_nmea_parser_parse_rmc():
    state = NmeaState()
    nmea_parser = NmeaParser()
    sentence = "$GPRMC,164824.00,A,5049.65778,N,00722.80053,E,36.793,265.08,180818,,,A*50"
    state = nmea_parser.parse(state, start_update_time, sentence)
    assert state.update_time == start_update_time
    assert state.gps_time == datetime(2018, 8, 18, 16, 48, 24)
    assert state.latitude == pytest.approx(50.82762967)
    assert state.longitude == pytest.approx(7.380008833)
    assert state.speed == pytest.approx(36.793)
    assert state.course == pytest.approx(265.08)


def test_nmea_parser_parse_gsa():
    state = NmeaState()
    nmea_parser = NmeaParser()
    sentences = ["$GPGSV,4,1,15,01,47,141,47,03,82,041,48,06,21,306,,09,23,209,35*78",
                 "$GPGSV,4,2,15,11,24,162,30,12,05,339,,14,16,045,11,17,42,266,41*70",
                 "$GPGSV,4,3,15,18,19,138,33,19,35,298,26,22,59,082,35,23,53,192,43*72",
                 "$GPGSV,4,4,15,25,00,018,,31,24,061,13,33,28,208,30*41",
                 "$GPGSA,A,3,11,22,18,03,14,01,09,31,23,19,17,,2.43,1.32,2.04*0B"]
    for sentence in sentences:
        state = nmea_parser.parse(state, start_update_time, sentence)
    active_satellites_count = len([satellite for satellite in state.satellites if satellite.is_active])
    assert active_satellites_count == 11
    assert state.update_time == start_update_time
    assert state.gps_time is None
    assert state.positional_dilution_of_precision == pytest.approx(2.43)
    assert state.horizontal_dilution_of_precision == pytest.approx(1.32)
    assert state.vertical_dilution_of_precision == pytest.approx(2.04)


def test_nmea_parser_parse_gga():
    state = NmeaState()
    nmea_parser = NmeaParser()
    sentence = "$GPGGA,164824.00,5049.65778,N,00722.80053,E,1,11,1.32,101.7,M,46.8,M,,*56"
    state = nmea_parser.parse(state, start_update_time, sentence)
    print(state)
    assert state.update_time == start_update_time
    assert state.latitude == pytest.approx(50.82762967)
    assert state.longitude == pytest.approx(7.380008833)
    assert state.height_above_sea_level == pytest.approx(101.7)
    assert state.geoidal_separation == pytest.approx(46.8)
    assert state.horizontal_dilution_of_precision == pytest.approx(1.32)
    assert state.gps_quality == 1


def test_nmea_parser_parse_gll():
    state = NmeaState()
    nmea_parser = NmeaParser()
    sentence = "$GPGLL,5049.65778,N,00722.80053,E,164824.00,A,A*6E"
    state = nmea_parser.parse(state, start_update_time, sentence)
    assert state.update_time == start_update_time
    assert state.gps_time is None
    assert state.latitude == pytest.approx(50.82762967)
    assert state.longitude == pytest.approx(7.380008833)


def test_nmea_parser_parse_vtg():
    state = NmeaState()
    nmea_parser = NmeaParser()
    sentence = "$GPVTG,263.92,T,,M,36.590,N,67.764,K,A*3C"
    state = nmea_parser.parse(state, start_update_time, sentence)
    assert state.speed == pytest.approx(36.59)
    assert state.course == pytest.approx(263.92)
