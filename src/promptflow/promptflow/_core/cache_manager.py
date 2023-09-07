# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import dataclass
from typing import Callable

from promptflow.contracts.run_info import RunInfo

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
        # TODO: Implement cache related logic.
        return DummyCacheManager()

    @staticmethod
    def init_dummy() -> "AbstractCacheManager":
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
