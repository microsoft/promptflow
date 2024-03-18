from unittest.mock import patch

import pytest

from promptflow._utils.process_utils import get_available_max_worker_count


class TestProcessUtils:
    @pytest.mark.parametrize(
        "available_memory, process_memory, expected_max_worker_count, actual_calculate_worker_count",
        [
            (128.0, 64.0, 2, 2),  # available_memory/process_memory > 1
            (63.0, 64.0, 1, 0),  # available_memory/process_memory < 1
        ],
    )
    def test_get_available_max_worker_count(
        self, available_memory, process_memory, expected_max_worker_count, actual_calculate_worker_count
    ):
        with patch("psutil.virtual_memory") as mock_mem:
            mock_mem.return_value.available = available_memory * 1024 * 1024
            with patch("psutil.Process") as mock_process:
                mock_process.return_value.memory_info.return_value.rss = process_memory * 1024 * 1024
                with patch("promptflow._utils.process_utils.bulk_logger") as mock_logger:
                    mock_logger.warning.return_value = None
                    estimated_available_worker_count = get_available_max_worker_count(mock_logger)
                    assert estimated_available_worker_count == expected_max_worker_count
                    if actual_calculate_worker_count < 1:
                        mock_logger.warning.assert_called_with(
                            f"Current system's available memory is {available_memory}MB, less than the memory "
                            f"{process_memory}MB required by the process. The maximum available worker count is 1."
                        )
                    else:
                        mock_logger.info.assert_called_with(
                            f"Current system's available memory is {available_memory}MB, "
                            f"memory consumption of current process is {process_memory}MB, "
                            f"estimated available worker count is {available_memory}/{process_memory} "
                            f"= {actual_calculate_worker_count}"
                        )
