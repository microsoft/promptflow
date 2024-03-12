from http import HTTPStatus
from typing import Any, Dict, Optional, Union

import httpx

from ....utils import _request_wrapper
from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.run_dict import RunDict
from ...types import Response


def _get_kwargs(
    name: str,
) -> Dict[str, Any]:
    _kwargs: Dict[str, Any] = {
        "method": "delete",
        "url": "/Runs/{name}".format(
            name=name,
        ),
    }

    return _kwargs


def _parse_response(*, client: Union[AuthenticatedClient, Client], response: httpx.Response) -> Optional[RunDict]:
    if response.status_code == HTTPStatus.NO_CONTENT:
        response_204 = RunDict.from_dict(response.json())

        return response_204
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: Union[AuthenticatedClient, Client], response: httpx.Response) -> Response[RunDict]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


@_request_wrapper()
def sync_detailed(
    name: str,
    *,
    client: Union[AuthenticatedClient, Client],
    stream: bool = False,
) -> Response[RunDict]:
    """Delete run

    Args:
        name (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[RunDict]
    """

    kwargs = _get_kwargs(
        name=name,
    )

    if stream:
        return client.get_httpx_client().stream(**kwargs)
    else:
        response = client.get_httpx_client().request(
            **kwargs,
        )
        return _build_response(client=client, response=response)


@_request_wrapper()
def sync(
    name: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[RunDict]:
    """Delete run

    Args:
        name (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        RunDict
    """

    return sync_detailed(
        name=name,
        client=client,
    ).parsed


@_request_wrapper()
async def asyncio_detailed(
    name: str,
    *,
    client: Union[AuthenticatedClient, Client],
    stream: bool = False,
) -> Response[RunDict]:
    """Delete run

    Args:
        name (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[RunDict]
    """

    kwargs = _get_kwargs(
        name=name,
    )
    if stream:
        with await client.get_httpx_client().stream(**kwargs) as response:
            return _build_response(client=client, response=response)
    else:
        response = await client.get_async_httpx_client().request(**kwargs)

        return _build_response(client=client, response=response)


@_request_wrapper()
async def asyncio(
    name: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[RunDict]:
    """Delete run

    Args:
        name (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        RunDict
    """

    return (
        await asyncio_detailed(
            name=name,
            client=client,
        )
    ).parsed
