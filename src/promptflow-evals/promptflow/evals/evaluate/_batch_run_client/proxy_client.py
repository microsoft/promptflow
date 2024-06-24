# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
import os

import numpy as np

from promptflow.client import PFClient
from promptflow.tracing import ThreadPoolExecutorWithContext as ThreadPoolExecutor

from ..._constants import BATCH_RUN_TIMEOUT_DEFAULT, BATCH_RUN_TIMEOUT_ENV_VAR

LOGGER = logging.getLogger(__name__)


class ProxyRun:
    def __init__(self, run, **kwargs):
        self.run = run


class ProxyClient:
    def __init__(self, pf_client: PFClient):
        self._pf_client = pf_client
        self._thread_pool = ThreadPoolExecutor(thread_name_prefix="evaluators_thread")

    def run(self, flow, data, column_mapping=None, **kwargs):
        eval_future = self._thread_pool.submit(
            self._pf_client.run, flow, data=data, column_mapping=column_mapping, **kwargs
        )
        return ProxyRun(run=eval_future)

    def get_details(self, proxy_run, all_results=False):
        batch_run_timeout = int(os.getenv(BATCH_RUN_TIMEOUT_ENV_VAR, BATCH_RUN_TIMEOUT_DEFAULT))
        run = proxy_run.run.result(timeout=batch_run_timeout)
        result_df = self._pf_client.get_details(run, all_results=all_results)
        result_df.replace("(Failed)", np.nan, inplace=True)
        return result_df

    def get_metrics(self, proxy_run):
        batch_run_timeout = int(os.getenv(BATCH_RUN_TIMEOUT_ENV_VAR, BATCH_RUN_TIMEOUT_DEFAULT))
        run = proxy_run.run.result(timeout=batch_run_timeout)
        return self._pf_client.get_metrics(run)
