import os

from tools.run_studio_dev import _parse_windows_netstat_pids, is_process_running


def test_parse_windows_netstat_pids_accepts_localized_listener_state():
    output = """
      TCP    0.0.0.0:7893           0.0.0.0:0              ABHÖREN         22312
      TCP    127.0.0.1:63828        127.0.0.1:7893         WARTEND         0
      TCP    [::]:7893              [::]:0                 LISTENING       22312
    """

    assert _parse_windows_netstat_pids(output, 7893) == [22312]


def test_is_process_running_detects_current_process():
    assert is_process_running(os.getpid())
