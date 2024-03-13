from http import HTTPStatus
from typing import Any, Dict, List, Optional, Union, cast

import httpx

from ....utils import _request_wrapper
from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.connection import Connection
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    working_directory: Union[Unset, str] = UNSET,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {}

    params["working_directory"] = working_directory

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: Dict[str, Any] = {
        "method": "get",
        "url": "/Connections/",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[Union[Any, List["Connection"]]]:
    if response.status_code == HTTPStatus.OK:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = Connection.from_dict(response_200_item_data)

            response_200.append(response_200_item)

        return response_200
    if response.status_code == HTTPStatus.FORBIDDEN:
        response_403 = cast(Any, None)
        return response_403
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[Union[Any, List["Connection"]]]:
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
    working_directory: Union[Unset, str] = UNSET,
    stream: bool = False,
) -> Response[Union[Any, List["Connection"]]]:
    """List all connection

    Args:
        working_directory (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[Any, List['Connection']]]
    """

    kwargs = _get_kwargs(
        working_directory=working_directory,
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
    *,
    client: Union[AuthenticatedClient, Client],
    working_directory: Union[Unset, str] = UNSET,
) -> Optional[Union[Any, List["Connection"]]]:
    """List all connection

    Args:
        working_directory (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[Any, List['Connection']]
    """

    return sync_detailed(
        client=client,
        working_directory=working_directory,
    ).parsed


@_request_wrapper()
async def asyncio_detailed(
    *,
    client: Union[AuthenticatedClient, Client],
    working_directory: Union[Unset, str] = UNSET,
    stream: bool = False,
) -> Response[Union[Any, List["Connection"]]]:
    """List all connection

    Args:
        working_directory (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[Any, List['Connection']]]
    """

    kwargs = _get_kwargs(
        working_directory=working_directory,
    )
    if stream:
        with await client.get_httpx_client().stream(**kwargs) as response:
            return _build_response(client=client, response=response)
    else:
        response = await client.get_async_httpx_client().request(**kwargs)

        return _build_response(client=client, response=response)


@_request_wrapper()
async def asyncio(
    *,
    client: Union[AuthenticatedClient, Client],
    working_directory: Union[Unset, str] = UNSET,
) -> Optional[Union[Any, List["Connection"]]]:
    """List all connection

    Args:
        working_directory (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[Any, List['Connection']]
    """

    return (
        await asyncio_detailed(
            client=client,
            working_directory=working_directory,
        )
    ).parsed
