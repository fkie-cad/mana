import json

from mana.method.method import Method, AverageMethod, GroupMethod, OrGroupMethod, AndGroupMethod, \
    AverageGroupMethod, MultipleReceiversMethod, PhysicalSpeedLimitMethod, PhysicalRateOfTurnLimitMethod, \
    PhysicalHeightLimitMethod, PhysicalEnvironmentLimitMethod, OrbitPositionsMethod, \
    TimeDriftMethod, CarrierToNoiseDensityMethod

method_name_to_class_dict = {
    "MultipleReceiversMethod".lower(): MultipleReceiversMethod,
    "PhysicalSpeedLimitMethod".lower(): PhysicalSpeedLimitMethod,
    "PhysicalRateOfTurnLimitMethod".lower(): PhysicalRateOfTurnLimitMethod,
    "PhysicalHeightLimitMethod".lower(): PhysicalHeightLimitMethod,
    "PhysicalEnvironmentLimitMethod".lower(): PhysicalEnvironmentLimitMethod,
    "OrbitPositionsMethod".lower(): OrbitPositionsMethod,
    "TimeDriftMethod".lower(): TimeDriftMethod,
    "CarrierToNoiseDensityMethod".lower(): CarrierToNoiseDensityMethod
}


def method_name_to_class(name):
    return method_name_to_class_dict[name.lower()]


def load_methods_json(filepath):
    with open(filepath) as f:
        data = json.load(f)

    device_ids = data['device_ids']
    method_classes = [method_name_to_class(name) for name in data['methods']]
    method_options = {}
    for key, value in data['options'].items():
        if isinstance(value, dict):
            method_options[key] = {}
            for k, v in value.items():
                if "," in k:
                    k = tuple(k.replace(" ", "").split(","))
                    assert len(k) == 2
                method_options[key][k] = v
        else:
            method_options[key] = value

    return device_ids, method_classes, method_options
