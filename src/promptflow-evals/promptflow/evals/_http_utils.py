# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


from functools import wraps
from typing import Any, Awaitable, Callable, Dict, MutableMapping, Optional

from azure.core.configuration import Configuration
from azure.core.pipeline import AsyncPipeline, Pipeline
from azure.core.pipeline.policies import (
    AsyncRedirectPolicy,
    AsyncRetryPolicy,
    CustomHookPolicy,
    HeadersPolicy,
    HttpLoggingPolicy,
    NetworkTraceLoggingPolicy,
    ProxyPolicy,
    RedirectPolicy,
    RetryPolicy,
    UserAgentPolicy,
)
from azure.core.pipeline.transport import (  # pylint: disable=non-abstract-transport-import,no-name-in-module
    AsyncHttpTransport,
    AsyncioRequestsTransport,
    HttpTransport,
    RequestsTransport,
)
from azure.core.rest import AsyncHttpResponse, HttpRequest, HttpResponse
from azure.core.rest._rest_py3 import ContentType, FilesType, ParamsType
from typing_extensions import Self

from promptflow.evals._user_agent import USER_AGENT


def _request_fn(f: Callable[["HttpPipeline"], None]):
    """Decorator to generate convenience methods for HTTP method.

    :param Callable[["HttpPipeline"],None] f: A HttpPipeline classmethod to wrap.
        The f.__name__ is the HTTP method used
    :return: A wrapped callable that sends a `f.__name__` request
    :rtype: Callable
    """

    @wraps(f)
    def request_fn(
        self: "HttpPipeline",
        url: str,
        *,
        params: Optional[ParamsType] = None,
        headers: Optional[MutableMapping[str, str]] = None,
        json: Any = None,
        content: Optional[ContentType] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[FilesType] = None,
        **kwargs,
    ) -> HttpResponse:
        return self.request(
            f.__name__.upper(),
            url,
            params=params,
            headers=headers,
            json=json,
            content=content,
            data=data,
            files=files,
            **kwargs,
        )

    return request_fn


def _async_request_fn(f: Callable[["AsyncHttpPipeline"], Awaitable[None]]):
    """Decorator to generate convenience methods for HTTP method.

    :param Callable[["HttpPipeline"],None] f: A HttpPipeline classmethod to wrap.
        The f.__name__ is the HTTP method used
    :return: A wrapped callable that sends a `f.__name__` request
    :rtype: Callable
    """

    @wraps(f)
    async def request_fn(
        self: "AsyncHttpPipeline",
        url: str,
        *,
        params: Optional[ParamsType] = None,
        headers: Optional[MutableMapping[str, str]] = None,
        json: Any = None,
        content: Optional[ContentType] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[FilesType] = None,
        **kwargs,
    ) -> AsyncHttpResponse:
        return await self.request(
            f.__name__.upper(),
            url,
            params=params,
            headers=headers,
            json=json,
            content=content,
            data=data,
            files=files,
            **kwargs,
        )

    return request_fn


class HttpPipeline(Pipeline):
    """A *very* thin wrapper over azure.core.pipeline.Pipeline that facilitates sending miscellaneous http requests by
    adding:

    * A requests-style api for sending http requests
    * Facilities for populating policies for the client, include defaults,
     and re-using policies from an existing client.
    """

    def __init__(
        self,
        *,
        transport: Optional[HttpTransport] = None,
        config: Optional[Configuration] = None,
        user_agent_policy: Optional[UserAgentPolicy] = None,
        headers_policy: Optional[HeadersPolicy] = None,
        proxy_policy: Optional[ProxyPolicy] = None,
        logging_policy: Optional[NetworkTraceLoggingPolicy] = None,
        http_logging_policy: Optional[HttpLoggingPolicy] = None,
        retry_policy: Optional[RetryPolicy] = None,
        custom_hook_policy: Optional[CustomHookPolicy] = None,
        redirect_policy: Optional[RedirectPolicy] = None,
        **kwargs,
    ):
        """

        :param HttpTransport transport: Http Transport used for requests, defaults to RequestsTransport
        :param Configuration config:
        :param UserAgentPolicy user_agent_policy:
        :param HeadersPolicy headers_policy:
        :param ProxyPolicy proxy_policy:
        :param NetworkTraceLoggingPolicy logging_policy:
        :param HttpLoggingPolicy http_logging_policy:
        :param RetryPolicy retry_policy:
        :param CustomHookPolicy custom_hook_policy:
        :param RedirectPolicy redirect_policy:
        """
        config = config or Configuration()
        config.headers_policy = headers_policy or config.headers_policy or HeadersPolicy(**kwargs)
        config.proxy_policy = proxy_policy or config.proxy_policy or ProxyPolicy(**kwargs)
        config.redirect_policy = redirect_policy or config.redirect_policy or RedirectPolicy(**kwargs)
        config.retry_policy = retry_policy or config.retry_policy or RetryPolicy(**kwargs)
        config.custom_hook_policy = custom_hook_policy or config.custom_hook_policy or CustomHookPolicy(**kwargs)
        config.logging_policy = logging_policy or config.logging_policy or NetworkTraceLoggingPolicy(**kwargs)
        config.http_logging_policy = http_logging_policy or config.http_logging_policy or HttpLoggingPolicy(**kwargs)
        config.user_agent_policy = user_agent_policy or config.user_agent_policy or UserAgentPolicy(**kwargs)
        config.polling_interval = kwargs.get("polling_interval", 30)

        super().__init__(
            # RequestsTransport normally should not be imported outside of azure.core, since transports
            # are meant to be user configurable.
            # RequestsTransport is only used in this file as the default transport when not user specified.
            transport=transport or RequestsTransport(**kwargs),
            policies=[
                config.headers_policy,
                config.user_agent_policy,
                config.proxy_policy,
                config.redirect_policy,
                config.retry_policy,
                config.authentication_policy,
                config.custom_hook_policy,
                config.logging_policy,
            ],
        )

        self._config = config

    def with_policies(self, **kwargs) -> Self:
        """A named constructor which facilitates creating a new pipeline using an existing one as a base.

           Accepts the same parameters as __init__

        :return: new Pipeline object with combined config of current object
            and specified overrides
        :rtype: Self
        """
        cls = self.__class__
        return cls(config=self._config, transport=kwargs.pop("transport", self._transport), **kwargs)

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[ParamsType] = None,
        headers: Optional[MutableMapping[str, str]] = None,
        json: Any = None,
        content: Optional[ContentType] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[FilesType] = None,
        **kwargs,
    ) -> HttpResponse:

        request = HttpRequest(
            method,
            url,
            params=params,
            headers=headers,
            json=json,
            content=content,
            data=data,
            files=files,
        )

        return self.run(request, **kwargs).http_response

    @_request_fn
    def delete(self) -> None:
        """Send a DELETE request."""

    @_request_fn
    def put(self) -> None:
        """Send a PUT request."""

    @_request_fn
    def get(self) -> None:
        """Send a GET request."""

    @_request_fn
    def post(self) -> None:
        """Send a POST request."""

    @_request_fn
    def head(self) -> None:
        """Send a HEAD request."""

    @_request_fn
    def options(self) -> None:
        """Send a OPTIONS request."""

    @_request_fn
    def patch(self) -> None:
        """Send a PATCH request."""


class AsyncHttpPipeline(AsyncPipeline):
    """A *very* thin wrapper over azure.core.pipeline.AsyncPipeline that facilitates sending miscellaneous
    http requests by adding:

    * A requests-style api for sending http requests
    * Facilities for populating policies for the client, include defaults,
     and re-using policies from an existing client.
    """

    def __init__(
        self,
        *,
        transport: Optional[AsyncHttpTransport] = None,
        config: Optional[Configuration] = None,
        user_agent_policy: Optional[UserAgentPolicy] = None,
        headers_policy: Optional[HeadersPolicy] = None,
        proxy_policy: Optional[ProxyPolicy] = None,
        logging_policy: Optional[NetworkTraceLoggingPolicy] = None,
        http_logging_policy: Optional[HttpLoggingPolicy] = None,
        retry_policy: Optional[AsyncRetryPolicy] = None,
        custom_hook_policy: Optional[CustomHookPolicy] = None,
        redirect_policy: Optional[AsyncRedirectPolicy] = None,
        **kwargs,
    ):
        """

        :param HttpTransport transport: Http Transport used for requests, defaults to RequestsTransport
        :param Configuration config:
        :param UserAgentPolicy user_agent_policy:
        :param HeadersPolicy headers_policy:
        :param ProxyPolicy proxy_policy:
        :param NetworkTraceLoggingPolicy logging_policy:
        :param HttpLoggingPolicy http_logging_policy:
        :param AsyncRetryPolicy retry_policy:
        :param CustomHookPolicy custom_hook_policy:
        :param AsyncRedirectPolicy redirect_policy:
        """
        config = config or Configuration()
        config.headers_policy = headers_policy or config.headers_policy or HeadersPolicy(**kwargs)
        config.proxy_policy = proxy_policy or config.proxy_policy or ProxyPolicy(**kwargs)
        config.redirect_policy = redirect_policy or config.redirect_policy or AsyncRedirectPolicy(**kwargs)
        config.retry_policy = retry_policy or config.retry_policy or AsyncRetryPolicy(**kwargs)
        config.custom_hook_policy = custom_hook_policy or config.custom_hook_policy or CustomHookPolicy(**kwargs)
        config.logging_policy = logging_policy or config.logging_policy or NetworkTraceLoggingPolicy(**kwargs)
        config.http_logging_policy = http_logging_policy or config.http_logging_policy or HttpLoggingPolicy(**kwargs)
        config.user_agent_policy = user_agent_policy or config.user_agent_policy or UserAgentPolicy(**kwargs)
        config.polling_interval = kwargs.get("polling_interval", 30)

        super().__init__(
            # AsyncioRequestsTransport normally should not be imported outside of azure.core, since transports
            # are meant to be user configurable.
            # AsyncioRequestsTransport is only used in this file as the default transport when not user specified.
            transport=transport or AsyncioRequestsTransport(**kwargs),
            policies=[
                config.headers_policy,
                config.user_agent_policy,
                config.proxy_policy,
                config.redirect_policy,
                config.retry_policy,
                config.authentication_policy,
                config.custom_hook_policy,
                config.logging_policy,
            ],
        )

        self._config = config

    def with_policies(self, **kwargs) -> Self:
        """A named constructor which facilitates creating a new pipeline using an existing one as a base.

           Accepts the same parameters as __init__

        :return: new Pipeline object with combined config of current object
            and specified overrides
        :rtype: Self
        """
        cls = self.__class__
        return cls(config=self._config, transport=kwargs.pop("transport", self._transport), **kwargs)

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[ParamsType] = None,
        headers: Optional[MutableMapping[str, str]] = None,
        json: Any = None,
        content: Optional[ContentType] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[FilesType] = None,
        **kwargs,
    ) -> AsyncHttpResponse:

        request = HttpRequest(
            method,
            url,
            params=params,
            headers=headers,
            json=json,
            content=content,
            data=data,
            files=files,
        )

        return (await self.run(request, **kwargs)).http_response

    @_async_request_fn
    async def delete(self) -> None:
        """Send a DELETE request."""

    @_async_request_fn
    async def put(self) -> None:
        """Send a PUT request."""

    @_async_request_fn
    async def get(self) -> None:
        """Send a GET request."""

    @_async_request_fn
    async def post(self) -> None:
        """Send a POST request."""

    @_async_request_fn
    async def head(self) -> None:
        """Send a HEAD request."""

    @_async_request_fn
    async def options(self) -> None:
        """Send a OPTIONS request."""

    @_async_request_fn
    async def patch(self) -> None:
        """Send a PATCH request."""


def get_http_client() -> HttpPipeline:
    """Get an HttpPipeline configured with common policies.

    :returns: An HttpPipeline with a set of applied policies:
    :rtype: HttpPipeline
    """
    return HttpPipeline(user_agent_policy=UserAgentPolicy(base_user_agent=USER_AGENT))


def get_async_http_client() -> AsyncHttpPipeline:
    """Get an AsyncHttpPipeline configured with common policies.

    :returns: An AsyncHttpPipeline with a set of applied policies:
    :rtype: AsyncHttpPipeline
    """
    return AsyncHttpPipeline(user_agent_policy=UserAgentPolicy(base_user_agent=USER_AGENT))
