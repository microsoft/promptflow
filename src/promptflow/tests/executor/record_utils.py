from pathlib import Path
from unittest.mock import patch

from promptflow.tracing._integrations._openai_injector import inject_openai_api

try:
    from promptflow.recording.record_mode import is_live, is_record, is_replay
except ImportError:
    # Run test in empty mode if promptflow-recording is not installed

    def is_live():
        return False

    def is_record():
        return False

    def is_replay():
        return False


PROMPTFLOW_ROOT = Path(__file__) / "../../.."
RECORDINGS_TEST_CONFIGS_ROOT = Path(PROMPTFLOW_ROOT / "../promptflow-recording/recordings/local").resolve()


def setup_recording():
    patches = []

    def start_patches(patch_targets):
        # Functions to setup the mock for list of targets
        for target, mock_func in patch_targets.items():
            patcher = patch(target, mock_func)
            patches.append(patcher)
            patcher.start()

    if is_replay() or is_record():
        # For replay and record mode, we setup two patches:
        # 1) mocked_tool setup
        # 2) openai_injector realted mock
        from promptflow.recording.local import (
            RecordStorage,
            inject_async_with_recording,
            inject_sync_with_recording,
            mock_tool,
        )

        file_path = RECORDINGS_TEST_CONFIGS_ROOT / "executor_node_cache.shelve"
        RecordStorage.get_instance(file_path)

        from promptflow._core.tool import tool as original_tool

        mocked_tool = mock_tool(original_tool)
        patch_targets = {
            "promptflow._core.tool.tool": mocked_tool,
            "promptflow._internal.tool": mocked_tool,
            "promptflow.tool": mocked_tool,
            "promptflow.core.tool": mocked_tool,
            "promptflow.tracing._integrations._openai_injector.inject_sync": inject_sync_with_recording,
            "promptflow.tracing._integrations._openai_injector.inject_async": inject_async_with_recording,
        }
        start_patches(patch_targets)
        inject_openai_api()

    if is_live():
        # For live mode, we setup openai_injector mock for token collection purpose
        from promptflow.recording.local import inject_async_with_recording, inject_sync_with_recording

        patch_targets = {
            "promptflow.tracing._integrations._openai_injector.inject_sync": inject_sync_with_recording,
            "promptflow.tracing._integrations._openai_injector.inject_async": inject_async_with_recording,
        }
        start_patches(patch_targets)
        inject_openai_api()

    return patches
