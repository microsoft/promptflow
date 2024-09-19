# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging

from aiohttp import TraceConfig
from aiohttp_retry import RandomRetry, RetryClient


class AsyncHTTPClientWithRetry:
    """Async HTTP client with retry configuration and request logging.

    :param n_retry: Number of retries to attempt
    :type n_retry: int
    :param retry_timeout: Timeout between retries, in seconds
    :type retry_timeout: int
    :param logger: The logger object to use for request logging
    :type logger: logging.Logger
    :param retry_options: The retry options. Defaults to None.
    :type retry_options: Optional[aiohttp_retry.retry_options.BaseRandomRetry]
    """
    def __init__(self, n_retry: int, retry_timeout: int, logger: logging.Logger, retry_options=None):
        self.attempts = n_retry
        self.logger = logger

        # Set up async HTTP client with retry

        trace_config = TraceConfig()  # set up request logging
        trace_config.on_request_end.append(self.delete_auth_header)
        if retry_options is None:
            retry_options = RandomRetry(  # set up retry configuration
                statuses=[104, 408, 409, 429, 500, 502, 503, 504],  # on which statuses to retry
                attempts=n_retry,
                min_timeout=retry_timeout,
                max_timeout=retry_timeout,
            )

        self.client = RetryClient(trace_configs=[trace_config], retry_options=retry_options)

    async def on_request_start(self, session, trace_config_ctx, params):  # pylint: disable=unused-argument
        """Build a new trace context from the config and log the request.

        :param session: The aiohttp client session. This parameter is not used in this method;
            however, it must be included to match the method signature of the parent class.
        :type session: aiohttp.ClientSession
        :param trace_config_ctx: The trace config context
        :type trace_config_ctx: Any
        :param params: The request parameters
        :type params: Any
        """
        current_attempt = trace_config_ctx.trace_request_ctx["current_attempt"]
        self.logger.info("[ATTEMPT %s] Sending %s request to %s" % (current_attempt, params.method, params.url))

    async def delete_auth_header(self, session, trace_config_ctx, params):  # pylint: disable=unused-argument
        """Delete authorization header from request headers

        If set, the "Authorization" and "api-key" headers is removed from the request headers.

        :param session: The aiohttp client session. This parameter is not used in this method;
            however, it must be included to match the method signature of the parent class.
        :type session: aiohttp.ClientSession
        :param trace_config_ctx: The trace config context. This parameter is not used in this method;
            however, it must be included to match the method signature of the parent class.
        :type trace_config_ctx: Any
        :param params: The request parameters
        :type params: Any
        """
        request_headers = dict(params.response.request_info.headers)
        if "Authorization" in request_headers:
            del request_headers["Authorization"]
        if "api-key" in request_headers:
            del request_headers["api-key"]

    async def on_request_end(self, session, trace_config_ctx, params):  # pylint: disable=unused-argument
        """
        Retrieve current request trace and log the response.

        :param session: The aiohttp client session. This parameter is not used in this method;
            however, it must be included to match the method signature of the parent class.
        :type session: aiohttp.ClientSession
        :param trace_config_ctx: The trace config context
        :type trace_config_ctx: Any
        :param params: The request parameters
        :type params: Any
        """
        current_attempt = trace_config_ctx.trace_request_ctx["current_attempt"]
        request_headers = dict(params.response.request_info.headers)
        if "Authorization" in request_headers:
            del request_headers["Authorization"]  # hide auth token from logs
        if "api-key" in request_headers:
            del request_headers["api-key"]
        self.logger.info(
            "[ATTEMPT %s] For %s request to %s, received response with status %s and request headers: %s"
            % (current_attempt, params.method, params.url, params.response.status, request_headers)
        )
