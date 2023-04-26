import datetime
import math


def string_to_datetime(datetime_string):
    datetime_format = '%Y-%m-%d %H:%M:%S.%f'
    datetime_object = datetime.datetime.strptime(datetime_string, datetime_format)
    return datetime_object


def minimum_angle_difference(angle1, angle2):
    phi = abs(angle1 - angle2) % 360
    return 360 - phi if phi > 180 else phi


def is_state_sufficiently_defined(state, required_state_fields):
    if state is None:
        return False
    if not all(getattr(state, field) is not None for field in required_state_fields):
        return False
    return True


def is_state_different(state, reference_state, variable_state_fields):
    is_the_state_different = len(variable_state_fields) == 0
    for field in variable_state_fields:
        reference_value = getattr(reference_state, field)
        value = getattr(state, field)
        if value != reference_value:
            is_the_state_different = True
            break
    return is_the_state_different


def distance_between_geograpic_positions(latitude1, longitude1, latitude2, longitude2):
    latitude1 = math.radians(latitude1)
    latitude2 = math.radians(latitude2)
    dlon = math.radians(longitude2) - math.radians(longitude1)
    dlat = latitude2 - latitude1
    a = math.sin(dlat / 2) ** 2 + math.cos(latitude1) * math.cos(latitude2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = 6378100 * c
    return distance


def calculate_precision_recall_f1(tp, fp, fn):
    try:
        precision = tp / (tp + fp)
    except Exception:
        precision = None
    try:
        recall = tp / (tp + fn)
    except Exception:
        recall = None
    try:
        f1 = 2 * precision * recall / (precision + recall)
    except Exception:
        f1 = None
    return precision, recall, f1


def print_precision_recall_f1(precision, recall, f1):
    print("precision", precision)
    print("recall", recall)
    print("f1", f1)
