from datetime import datetime
from unittest import mock

from mana.feeder import LogFeeder, SerialFeeder, SerialThread


class LogFeederTestable(LogFeeder):

    def read_lines_from_log_file(self):
        return ["2018-01-01 12:00:00.0 PORT TEST"]


@mock.patch("mana.handler.Handler")
def test_log_feeder_run(handler_mock):
    feeder = LogFeederTestable(handler=handler_mock, log_file="testfile.log")
    feeder.run()
    handler_mock.handle.assert_called_with(time=datetime(2018, 1, 1, 12, 0), device_id="PORT", sentence="TEST")


@mock.patch("mana.handler.Handler")
@mock.patch("mana.feeder.SerialFeeder.create_serial_thread")
def test_serial_feeder_run(create_serial_thread_mock, handler_mock):
    handler_mock.ports = {"PORT1": None, "PORT2": None}
    feeder = SerialFeeder(handler=handler_mock, ports=["PORT1", "PORT2"])
    feeder.run()
    create_serial_thread_mock.assert_called()


class SerialThreadTestable(SerialThread):

    def __init__(self, handler, port, *args, **kwargs):
        super().__init__(handler, port, *args, *kwargs)
        self.boolean_generator = (i for i in [True, False])

    def is_running(self):
        return next(self.boolean_generator)

    def connect_to_serial_port(self):
        self.serial = mock.MagicMock()

    def read_line_from_serial_connection(self):
        return "TEST\n\r".encode()

    @staticmethod
    def current_datetime():
        return datetime(2018, 1, 1, 12, 0)


@mock.patch("mana.handler.Handler")
def test_serial_thread_run(handler_mock):
    serial_thread = SerialThreadTestable(handler_mock, "PORT")
    serial_thread.run()
    handler_mock.handle.assert_called_with(time=datetime(2018, 1, 1, 12, 0), device_id="PORT", sentence="TEST")
