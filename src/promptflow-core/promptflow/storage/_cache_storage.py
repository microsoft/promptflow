# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import dataclass
from datetime import datetime

from promptflow.contracts.run_info import RunInfo


@dataclass
class CacheRecord:
    run_id: str
    hash_id: str
    flow_run_id: str
    flow_id: str
    cache_string: str
    end_time: datetime


class AbstractCacheStorage:
    def get_cache_record_list(hash_id: str) -> CacheRecord:
        pass

    def persist_cache_result(run_info: RunInfo):
        pass
