# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
import tempfile
import threading

import pytest

from promptflow._utils.context_utils import _change_working_dir


class TestChangeWorkingDir:
    def test_basic(self, tmp_path):
        original = os.getcwd()
        with _change_working_dir(tmp_path, mkdir=False):
            assert os.getcwd() == str(tmp_path)
        assert os.getcwd() == original

    def test_restores_on_exception(self, tmp_path):
        original = os.getcwd()
        with pytest.raises(RuntimeError):
            with _change_working_dir(tmp_path, mkdir=False):
                raise RuntimeError("boom")
        assert os.getcwd() == original

    def test_mkdir(self, tmp_path):
        new_dir = tmp_path / "nested" / "dir"
        assert not new_dir.exists()
        with _change_working_dir(new_dir):
            assert new_dir.exists()

    def test_thread_safety_no_cwd_leakage(self, tmp_path):
        """Regression test for https://github.com/microsoft/promptflow/issues/3553.

        Concurrent threads must not observe each other's intermediate os.chdir state.
        Each thread changes to its own directory and verifies getcwd() inside the
        context manager matches what it set — not another thread's directory.
        """
        dirs = [tmp_path / f"dir_{i}" for i in range(10)]
        for d in dirs:
            d.mkdir()

        errors = []

        def worker(target_dir):
            with _change_working_dir(target_dir, mkdir=False):
                observed = os.getcwd()
                if observed != str(target_dir):
                    errors.append(f"expected {target_dir}, got {observed}")

        threads = [threading.Thread(target=worker, args=(d,)) for d in dirs]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread-safety violations: {errors}"
