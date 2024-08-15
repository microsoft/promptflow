# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import inspect
import logging
import os

import numpy as np

from promptflow.client import PFClient
from promptflow.tracing import ThreadPoolExecutorWithContext as ThreadPoolExecutor

LOGGER = logging.getLogger(__name__)


class ProxyRun:
    def __init__(self, run, **kwargs):
        self.run = run


class ProxyClient:
    def __init__(self, pf_client: PFClient):
        self._pf_client = pf_client
        self._thread_pool = ThreadPoolExecutor(thread_name_prefix="evaluators_thread")

    def run(self, flow, data, column_mapping=None, **kwargs):
        flow_to_run = flow
        if hasattr(flow, "_to_async"):
            flow_to_run = flow._to_async()

        batch_use_async = self._should_batch_use_async(flow_to_run)
        eval_future = self._thread_pool.submit(
            self._pf_client.run,
            flow_to_run,
            data=data,
            column_mapping=column_mapping,
            batch_use_async=batch_use_async,
            **kwargs
        )
        return ProxyRun(run=eval_future)

    def get_details(self, proxy_run, all_results=False):
        run = proxy_run.run.result()
        result_df = self._pf_client.get_details(run, all_results=all_results)
        result_df.replace("(Failed)", np.nan, inplace=True)
        return result_df

    def get_metrics(self, proxy_run):
        run = proxy_run.run.result()
        return self._pf_client.get_metrics(run)

    @staticmethod
    def _should_batch_use_async(flow):
        if os.getenv("PF_EVALS_BATCH_USE_ASYNC", "true").lower() == "true":
            if hasattr(flow, "__call__") and inspect.iscoroutinefunction(flow.__call__):
                return True
            elif inspect.iscoroutinefunction(flow):
                return True
            else:
                return False
        return False
