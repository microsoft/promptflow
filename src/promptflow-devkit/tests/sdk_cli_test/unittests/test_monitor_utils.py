import copy
import json
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from promptflow._sdk._utilities.monitor_utils import (
    DirectoryModificationMonitorTarget,
    JsonContentMonitorTarget,
    Monitor,
    MonitorTarget,
)

global_var = 0
global_var_2 = None


class DummyMonitorTarget(MonitorTarget):
    def get_key(self) -> str:
        return "dummy"

    def _update_stat(self, key: str, cache: dict) -> bool:
        global global_var
        if global_var == 0:
            return False
        if global_var == -1:
            raise RuntimeError("test")
        # reset global_var to 0 and trigger callback
        global_var = 0
        return True


def write_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def assert_update_cache(expected, extra_msg, cache, monitor_target):
    last_cache = copy.deepcopy(cache)
    result = monitor_target.update_cache(cache)
    if result == expected:
        return
    msg = f"{extra_msg}\n" f"Last cache: {json.dumps(last_cache)}\n" f"Current cache: {json.dumps(cache)}\n"
    raise AssertionError(msg)


@pytest.mark.unittest
class TestMonitorUtils:
    def test_directory_modification_monitor_target(self):
        cache = {}

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            monitor_target = DirectoryModificationMonitorTarget(
                target=temp_dir, relative_root_ignores=[".git", ".idea"]
            )

            assert_update_cache(False, "empty directory", cache, monitor_target)

            (temp_dir / "test.txt").touch()
            assert_update_cache(True, "file added", cache, monitor_target)
            assert_update_cache(False, "same content", cache, monitor_target)

            # wait for 0.1s to make sure the last modified time is different
            time.sleep(0.1)

            target_file = temp_dir / "test.txt"
            write_json(target_file, "test")
            assert_update_cache(
                True,
                "content changed on " + str(target_file.stat().st_mtime) + ": " + (temp_dir / "test.txt").read_text(),
                cache,
                monitor_target,
            )
            assert_update_cache(False, "same content", cache, monitor_target)

            # ignore empty directory creation
            (temp_dir / "new").mkdir()
            assert_update_cache(False, "shouldn't detect new directory", cache, monitor_target)
            (temp_dir / "new" / "test.txt").touch()
            assert_update_cache(True, "file in subdirectories added", cache, monitor_target)

            (temp_dir / ".git").mkdir()
            (temp_dir / ".git" / "test.txt").touch()
            (temp_dir / ".idea").mkdir()
            (temp_dir / ".idea" / "test.txt").touch()
            assert_update_cache(False, "ignore works for directories in root", cache, monitor_target)

            # ignore .git file in root
            (temp_dir / ".git").touch()
            assert_update_cache(False, "ignore works for files in root", cache, monitor_target)

            (temp_dir / ".git" / "new").mkdir()
            (temp_dir / ".git" / "new" / "test.txt").touch()
            assert_update_cache(False, "ignore works for sub directories under ignored root", cache, monitor_target)

            # ignore works in root only
            (temp_dir / "new" / ".idea").touch()
            assert_update_cache(True, "ignore works in root only", cache, monitor_target)

            (temp_dir / "test.txt").unlink()
            assert_update_cache(True, "file removed", cache, monitor_target)

    def test_content_modification_monitor_target(self):
        cache = {}

        with tempfile.TemporaryDirectory() as temp_dir:
            target_file = Path(temp_dir) / "test.json"
            monitor_target = JsonContentMonitorTarget(target=target_file, node_path=["key1", "key2"])

            assert_update_cache(True, "first time", cache, monitor_target)
            assert_update_cache(False, "still not exist", cache, monitor_target)

            data = {
                "key1": {
                    "key1": "value1",
                }
            }
            write_json(target_file, data)
            assert_update_cache(False, "no related content found", cache, monitor_target)

            data["key1"]["key2"] = "value2"
            write_json(target_file, data)
            assert_update_cache(True, "related content found", cache, monitor_target)

            # wait for 0.1s to make sure the last modified time is different
            time.sleep(0.1)
            data["key1"]["key2"] = "value3"
            write_json(target_file, data)
            assert_update_cache(
                True, f"related content changed:\ncurrent json content:{target_file.read_text()}", cache, monitor_target
            )

            data["key1"]["key1"] = "value2"
            write_json(target_file, data)
            assert_update_cache(False, "change not related", cache, monitor_target)

            # wait for 0.1s to make sure the last modified time is different
            time.sleep(0.1)
            del data["key1"]["key2"]
            write_json(target_file, data)
            assert_update_cache(True, "delete related", cache, monitor_target)

    def test_monitor(self, capsys):
        monitor = Monitor(
            targets=[DummyMonitorTarget()],
            target_callback=lambda: print("callback"),
        )
        with ThreadPoolExecutor() as executor:
            global global_var
            global_var = 0
            future = executor.submit(monitor.start_monitor, interval=0.05)

            try:
                # give monitor some time to start
                time.sleep(0.1)
                stdout, _ = capsys.readouterr()
                assert stdout == "callback\n", "callback for first run"

                global_var = 1
                time.sleep(0.1)
                assert global_var == 0, "reset global_var to 0"
                stdout, _ = capsys.readouterr()
                assert stdout == "callback\n", "callback is triggered"

                global_var = 0
                time.sleep(0.1)
                stdout, _ = capsys.readouterr()
                assert stdout == "", "no callback when no change"

                global_var = -1
                time.sleep(0.1)
                stdout, _ = capsys.readouterr()
                assert stdout == "", "no callback when exception is raised"

                global_var = 1
                time.sleep(0.1)
                assert global_var == 1, "monitor should stop when exception is raised"
                with pytest.raises(RuntimeError):
                    future.result()
            finally:
                # in case exception raised before monitor stops and hangs the test
                global_var = -1
                with pytest.raises(RuntimeError):
                    future.result()

    def test_monitor_with_last_callback_result(self):
        def callback_accept_last_result(last_result, *, step):
            global global_var_2
            if last_result is None:
                result = 0
            else:
                result = last_result + step
            global_var_2 = result
            return result

        monitor = Monitor(
            targets=[DummyMonitorTarget()],
            target_callback=callback_accept_last_result,
            target_callback_kwargs={"step": 2},
            inject_last_callback_result=True,
        )

        with ThreadPoolExecutor() as executor:
            global global_var
            global global_var_2
            global_var_2 = None
            global_var = 0
            future = executor.submit(monitor.start_monitor, interval=0.05)
            try:
                # give monitor some time to start
                time.sleep(0.1)
                assert global_var_2 == 0, "callback for first run"

                global_var = 1
                time.sleep(0.1)
                assert global_var_2 == 2, "callback for first run"

                global_var = 1
                time.sleep(0.1)
                assert global_var_2 == 4, "callback for first run"

                global_var = -1
                assert global_var_2 == 4, "no callback when exception is raised"

                with pytest.raises(RuntimeError):
                    future.result()
            finally:
                # in case exception raised before monitor stops and hangs the test
                global_var = -1
                with pytest.raises(RuntimeError):
                    future.result()
