import json
import os

from mana.feeder import PcapFeeder
from mana.handler import DetectionHandler
from mana.method import load_methods_json
from mana.utility import calculate_precision_recall_f1, print_precision_recall_f1


class Counter:

    def __init__(self):
        self.value = 0

    def increment_by_one(self, *args, **kwargs):
        self.value += 1

    def reset(self):
        self.value = 0


def is_pcap_spoofed(file, counter, handler):
    feeder = PcapFeeder(handler, file)
    feeder.run()
    return counter.value > 0


counter = Counter()
device_ids, method_classes, method_options = load_methods_json("methods.json")

base_path = "../data/dataset/"
with open(os.path.join(base_path, "dataset.json")) as json_file:
    data = json.load(json_file)

tp, fp, fn = 0, 0, 0
for entry in data:
    file = entry['filename']
    label = entry['label']

    counter.reset()
    handler = DetectionHandler(device_ids=device_ids, method_classes=method_classes,
                               method_options=method_options, on_spoofing_attack=counter.increment_by_one,
                               detection_threshold=0.1)

    spoofed = is_pcap_spoofed(os.path.join(base_path, file), counter, handler)
    if spoofed and label == "spoofed":
        tp += 1
    elif spoofed and label == "unspoofed":
        fp += 1
    elif not spoofed and label == "spoofed":
        fn += 1

precision, recall, f1 = calculate_precision_recall_f1(tp, fp, fn)
print_precision_recall_f1(precision, recall, f1)
