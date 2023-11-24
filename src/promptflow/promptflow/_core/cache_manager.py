# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import hashlib
import json
from dataclasses import dataclass
from typing import Callable, List

from promptflow._utils.logger_utils import flow_logger
from promptflow.contracts.run_info import RunInfo
from promptflow.storage import AbstractCacheStorage, AbstractRunStorage

PROMPTFLOW_HASH_ATTR = "__promptflow_hash_func"


def get_calculate_cache_func(tool_func):
    return getattr(tool_func, PROMPTFLOW_HASH_ATTR, None)


def set_calculate_cache_func(tool_func, calculate_cache_func):
    setattr(tool_func, PROMPTFLOW_HASH_ATTR, calculate_cache_func)


def enable_cache(calculate_cache_func):
    def decorator_enable_cache(func):
        set_calculate_cache_func(func, calculate_cache_func)
        return func

    return decorator_enable_cache


@dataclass
class CacheInfo:
    hash_id: str = None
    cache_string: str = None


@dataclass
class CacheResult:
    result: object = None
    cached_run_id: str = None
    cached_flow_run_id: str = None
    hit_cache: bool = False


class AbstractCacheManager:
    @staticmethod
    def init_from_env() -> "AbstractCacheManager":
        # TODO: Return CacheManager after local execution is enabled.
        return DummyCacheManager()

    def calculate_cache_info(self, flow_id: str, tool_method: Callable, args, kwargs) -> CacheInfo:
        raise NotImplementedError("AbstractCacheManager has not implemented method calculate_cache_info.")

    def get_cache_result(self, cache_info: CacheInfo) -> CacheResult:
        raise NotImplementedError("AbstractCacheManager has not implemented method get_cache_result.")

    def persist_result(self, run_info: RunInfo, hash_id: str, cache_string: str, flow_id: str):
        raise NotImplementedError("AbstractCacheManager has not implemented method persist_result.")


class DummyCacheManager(AbstractCacheManager):
    def __init__(self):
        pass

    def calculate_cache_info(self, flow_id: str, tool_method: Callable, args, kwargs) -> CacheInfo:
        return None

    def get_cache_result(self, cache_info: CacheInfo) -> CacheResult:
        return None

    def persist_result(self, run_info: RunInfo, hash_id: str, cache_string: str, flow_id: str):
        pass


class CacheManager(AbstractCacheManager):
    def __init__(self, run_storage: AbstractRunStorage, cache_storage: AbstractCacheStorage):
        self._run_storage = run_storage
        self._cache_storage = cache_storage

    def calculate_cache_info(self, flow_id: str, tool_method: Callable, args, kwargs) -> CacheInfo:
        cache_function = get_calculate_cache_func(tool_method)
        # Cache function is not registered with this tool.
        if cache_function is None:
            return None

        # Calculate cache string and hash id.
        try:
            cache_string = cache_function(*args, **kwargs)
        except Exception as ex:
            flow_logger.warning(f"Failed to calculate cache string. Exception: {ex}")
            return None

        # Add flow_id and tool_name in the cache string.
        # So that different flow_id and tool_name cannot reuse.
        other_cache_string = json.dumps(
            {
                "flow_id": flow_id,
                "tool_name": tool_method.__qualname__,
            }
        )
        cache_string += other_cache_string
        hash_id = self._calculate_hash_id(cache_string)
        return CacheInfo(hash_id=hash_id, cache_string=cache_string)

    def get_cache_result(self, cache_info: CacheInfo) -> CacheResult:
        hash_id = cache_info.hash_id

        # Query if cache result existed by hash_id.
        cache_result_list: List[CacheInfo] = self._cache_storage.get_cache_record_list(hash_id=hash_id)

        if len(cache_result_list) == 0:
            return None

        # Get the latest cache result.
        cache_result = sorted(cache_result_list, reverse=True, key=lambda i: i.end_time)[0]
        try:
            cached_run_info = self._run_storage.get_node_run(cache_result.run_id)
        except Exception as ex:
            flow_logger.warning(
                f"Failed to get cached run result. \
                            Run id:{cached_run_info.run_id}, flow run id: {cached_run_info.flow_run_id} \
                            Exception: {ex}"
            )
            return None

        flow_logger.info(
            f"Hit cached result of previous run: run id: \
                     {cached_run_info.run_id}, flow run id: {cached_run_info.flow_run_id}"
        )

        return CacheResult(
            result=cached_run_info.result,
            cached_run_id=cached_run_info.run_id,
            cached_flow_run_id=cached_run_info.flow_run_id,
            hit_cache=True,
        )

    def persist_result(self, run_info: RunInfo, cache_info: CacheInfo, flow_id: str):
        self._cache_storage.persist_cache_result(run_info, cache_info.hash_id, cache_info.cache_string, flow_id)

    @staticmethod
    def _calculate_hash_id(cache_string: str):
        return hashlib.sha1(cache_string.encode("utf-8")).hexdigest()
