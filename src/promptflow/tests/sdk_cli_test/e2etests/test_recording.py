from pathlib import Path

import pytest

from .test_cli import FLOWS_DIR, run_pf_command

RECORDINGS_TEST_CONFIGS_ROOT = "./tests/test_configs/node_recordings"


@pytest.mark.usefixtures(
    "use_secrets_config_file",
    "setup_local_connection",
    "install_custom_tool_pkg",
    "recording_injection",
    "recording_enabled",
)
@pytest.mark.cli_test
@pytest.mark.e2etest
class TestRecording:
    @pytest.mark.usefixtures("recording_enabled", "recording_file_override")
    def test_pf_flow_test_recording_enabled_and_override_recording(self):
        flow_name = "basic_with_builtin_llm_node"
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/{flow_name}",
        )
        output_path = Path(FLOWS_DIR) / flow_name / ".promptflow" / "flow.output.json"
        assert output_path.exists()
        log_path = Path(FLOWS_DIR) / flow_name / ".promptflow" / "flow.log"
        assert log_path.exists()
        record_path = Path(RECORDINGS_TEST_CONFIGS_ROOT) / "testcli_node_cache.shelve.dat"
        assert record_path.exists()

    @pytest.mark.usefixtures("replaying_enabled", "recording_file_override")
    def test_pf_flow_test_replay_enabled_and_override_recording(self):
        flow_name = "basic_with_builtin_llm_node"
        record_path = Path(RECORDINGS_TEST_CONFIGS_ROOT) / "testcli_node_cache.shelve.dat"
        if not record_path.exists():
            assert False

        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/basic_with_builtin_llm_node",
        )
        output_path = Path(FLOWS_DIR) / flow_name / ".promptflow" / "flow.output.json"
        assert output_path.exists()
        log_path = Path(FLOWS_DIR) / flow_name / ".promptflow" / "flow.log"
        assert log_path.exists()
