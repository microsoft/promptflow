import sys

from sdk_cli_test.conftest import setup_recording_injection_if_enabled
from sdk_cli_test.recording_utilities import is_record

from promptflow._sdk._submitter.experiment_orchestrator import main
from promptflow._sdk._submitter.utils import _start_process_in_background


def mock_start_process_in_background(args, executable_path=None):
    if is_record():
        args[1] = __file__
    _start_process_in_background(args, executable_path)


if __name__ == "__main__":
    patches = setup_recording_injection_if_enabled()
    main(sys.argv[1:])
    for patcher in patches:
        patcher.stop()
