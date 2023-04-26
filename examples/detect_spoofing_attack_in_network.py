from mana.feeder import NetworkFeeder
from mana.handler import DetectionHandler
from mana.method import load_methods_json


def on_spoofing_attack(device_id, spoofing_indicator, method, state):
    print("Spoofing attack detected on {} at {}!".format(device_id, state.update_time))
    print("Method: {}".format(method))
    print("Spoofing indicator value: {}".format(spoofing_indicator))
    print("Last parsed sentence: {}".format(state.last_nmea_sentence))


device_ids, method_classes, method_options = load_methods_json("methods.json")

handler = DetectionHandler(device_ids=device_ids, method_classes=method_classes,
                           method_options=method_options, on_spoofing_attack=on_spoofing_attack,
                           detection_threshold=0.1)
feeder = NetworkFeeder(handler)
feeder.run()
