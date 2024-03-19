from http import HTTPStatus
from typing import Any, Dict, Optional, Union

import httpx

from ....utils import _request_wrapper
from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.telemetry import Telemetry
from ...types import Response


def _get_kwargs(
    *,
    body: Telemetry,
) -> Dict[str, Any]:
    headers: Dict[str, Any] = {}

    _kwargs: Dict[str, Any] = {
        "method": "post",
        "url": "/Telemetries/",
    }

    _body = body.to_dict()

    _kwargs["json"] = _body
    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(*, client: Union[AuthenticatedClient, Client], response: httpx.Response) -> Optional[Any]:
    if response.status_code == HTTPStatus.OK:
        return None
    if response.status_code == HTTPStatus.BAD_REQUEST:
        return None
    if response.status_code == HTTPStatus.FORBIDDEN:
        return None
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: Union[AuthenticatedClient, Client], response: httpx.Response) -> Response[Any]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


@_request_wrapper()
def sync_detailed(
    *,
    client: Union[AuthenticatedClient, Client],
    body: Telemetry,
    stream: bool = False,
) -> Response[Any]:
    """Create telemetry record

    Args:
        body (Telemetry):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    if stream:
        return client.get_httpx_client().stream(**kwargs)
    else:
        response = client.get_httpx_client().request(
            **kwargs,
        )
        return _build_response(client=client, response=response)


@_request_wrapper()
async def asyncio_detailed(
    *,
    client: Union[AuthenticatedClient, Client],
    body: Telemetry,
    stream: bool = False,
) -> Response[Any]:
    """Create telemetry record

    Args:
        body (Telemetry):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any]
    """

    kwargs = _get_kwargs(
        body=body,
    )
    if stream:
        with await client.get_httpx_client().stream(**kwargs) as response:
            return _build_response(client=client, response=response)
    else:
        response = await client.get_async_httpx_client().request(**kwargs)

        return _build_response(client=client, response=response)
