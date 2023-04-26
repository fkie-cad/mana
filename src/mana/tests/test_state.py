import datetime as dt

from mana.state import StateHistory


class DummyState:

    def __init__(self, number, update_time):
        self.number = number
        self.update_time = update_time


def test_state_history_default_parameters():
    state_history = StateHistory()
    assert state_history.max_state_history_time_span == 5


def test_state_history_add_state():
    state_history = StateHistory()
    expected_number_of_last_added_state = 59
    for i in range(expected_number_of_last_added_state + 1):
        state_history.add_state(DummyState(i, dt.datetime(2018, 1, 1, 0, 0, i)))
    number_of_last_added_state = state_history.state_history[0].number
    assert number_of_last_added_state == expected_number_of_last_added_state
    count_of_stored_states = len(state_history.state_history)
    assert count_of_stored_states == 6


def test_state_history_state_before_after():
    state_history = StateHistory()
    for i in [a for a in range(10) if a != 5]:
        state_history.add_state(DummyState(i, dt.datetime(2018, 1, 1, 0, 0, i)))
    time = dt.datetime(2018, 1, 1, 0, 0, 5)
    expected_state_time_before = dt.datetime(2018, 1, 1, 0, 0, 4)
    state_time_before = state_history.state_before(time).update_time
    assert state_time_before == expected_state_time_before
    expected_state_time_after = dt.datetime(2018, 1, 1, 0, 0, 6)
    state_time_after = state_history.state_after(time).update_time
    assert state_time_after == expected_state_time_after


def test_state_history_state():
    state_history = StateHistory()
    for i in range(10):
        state = DummyState(i, dt.datetime(2018, 1, 1, 0, 0, i))
        state_history.add_state(state)
    state = state_history.state(5)
    assert state.number == 5 - 1
