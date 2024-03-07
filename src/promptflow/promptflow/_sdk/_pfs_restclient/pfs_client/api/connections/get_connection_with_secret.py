from http import HTTPStatus
from typing import Any, Dict, Optional, Union, cast

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.connection_dict import ConnectionDict
from ...types import UNSET, Response, Unset


def _get_kwargs(
    name: str,
    *,
    working_directory: Union[Unset, str] = UNSET,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {}

    params["working_directory"] = working_directory

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: Dict[str, Any] = {
        "method": "get",
        "url": "/Connections/{name}/listsecrets".format(
            name=name,
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[Union[Any, ConnectionDict]]:
    if response.status_code == HTTPStatus.OK:
        response_200 = ConnectionDict.from_dict(response.json())

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
) -> Response[Union[Any, ConnectionDict]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    name: str,
    *,
    client: Union[AuthenticatedClient, Client],
    working_directory: Union[Unset, str] = UNSET,
) -> Response[Union[Any, ConnectionDict]]:
    """Get connection with secret

    Args:
        name (str):
        working_directory (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[Any, ConnectionDict]]
    """

    kwargs = _get_kwargs(
        name=name,
        working_directory=working_directory,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    name: str,
    *,
    client: Union[AuthenticatedClient, Client],
    working_directory: Union[Unset, str] = UNSET,
) -> Optional[Union[Any, ConnectionDict]]:
    """Get connection with secret

    Args:
        name (str):
        working_directory (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[Any, ConnectionDict]
    """

    return sync_detailed(
        name=name,
        client=client,
        working_directory=working_directory,
    ).parsed


async def asyncio_detailed(
    name: str,
    *,
    client: Union[AuthenticatedClient, Client],
    working_directory: Union[Unset, str] = UNSET,
) -> Response[Union[Any, ConnectionDict]]:
    """Get connection with secret

    Args:
        name (str):
        working_directory (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[Any, ConnectionDict]]
    """

    kwargs = _get_kwargs(
        name=name,
        working_directory=working_directory,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    name: str,
    *,
    client: Union[AuthenticatedClient, Client],
    working_directory: Union[Unset, str] = UNSET,
) -> Optional[Union[Any, ConnectionDict]]:
    """Get connection with secret

    Args:
        name (str):
        working_directory (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[Any, ConnectionDict]
    """

    return (
        await asyncio_detailed(
            name=name,
            client=client,
            working_directory=working_directory,
        )
    ).parsed
