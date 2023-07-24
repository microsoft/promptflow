import pytest
from datetime import datetime
from uuid import uuid4

from promptflow.storage.local_run_storage import LocalRunStorage
from promptflow.storage.cache_storage import LocalCacheStorage
from promptflow.core.cache_manager import CacheManager, enable_cache
from promptflow.contracts.run_info import RunInfo, Status


FLOW_ID = 'flow-id-value'
CALCULATED_CACHE_STRING = 'cache-string-value'
TOOL_RESULT = 'dummy result'


def _calculate_cache_string():
    return CALCULATED_CACHE_STRING


@enable_cache(_calculate_cache_string)
def dummy_tool():
    return TOOL_RESULT


def _generate_run_info() -> RunInfo:
    return RunInfo(
        node='dummy-node',
        flow_run_id='flow-run-id',
        run_id=str(uuid4()),  # Randome run id.
        status=Status.Completed,
        inputs=['input-value'],
        cached_run_id='',
        cached_flow_run_id='',
        output=dummy_tool(),
        metrics={},
        error=None,
        parent_run_id='parent-run-id',
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
        result=dummy_tool(),
    )


def _create_cache_manager():
    local_run_storage = LocalRunStorage(
        db_folder_path=None,
        db_name=None,
        test_mode=True
    )

    local_cache_storage = LocalCacheStorage(
        db_folder_path=None,
        db_name=None,
        test_mode=True
    )

    return CacheManager(local_run_storage, local_cache_storage)


@pytest.mark.unittest
class TestCacheManager:
    def test_calculate_cache_info(self):
        self.cache_manager = _create_cache_manager()
        cache_info = self.cache_manager.calculate_cache_info(
            FLOW_ID,
            tool_method=dummy_tool,
            args=[],
            kwargs=dict()
        )
        assert cache_info.cache_string is not None and cache_info.cache_string.startswith(CALCULATED_CACHE_STRING)
        assert cache_info.hash_id is not None
        return cache_info

    def test_get_cache_result(self):
        cache_info = self.test_calculate_cache_info()
        cache_result = self.cache_manager.get_cache_result(
            cache_info)
        # Miss the cache.
        assert cache_result is None

    def test_persist_result(self):
        cache_info = self.test_calculate_cache_info()
        run_info = _generate_run_info()
        self.cache_manager.persist_result(
            run_info,
            cache_info,
            FLOW_ID,
        )
        result_list = self.cache_manager._cache_storage.get_cache_record_list(cache_info.hash_id)
        assert len(result_list) == 1
        assert result_list[0].cache_string == cache_info.cache_string
        # Persist node run
        self.cache_manager._run_storage.persist_node_run(run_info)
        # Re-get cache result, the cache should be hit.
        cache_result = self.cache_manager.get_cache_result(cache_info)
        assert cache_result.hit_cache
        assert cache_result.result == TOOL_RESULT
        assert cache_result.cached_run_id == run_info.run_id
        assert cache_result.cached_flow_run_id == run_info.flow_run_id
