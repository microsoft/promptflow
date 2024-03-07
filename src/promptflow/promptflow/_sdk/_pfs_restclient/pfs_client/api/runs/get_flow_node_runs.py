from http import HTTPStatus
from typing import Any, Dict, List, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.run_dict import RunDict
from ...types import Response


def _get_kwargs(
    name: str,
    node_name: str,
) -> Dict[str, Any]:
    _kwargs: Dict[str, Any] = {
        "method": "get",
        "url": "/Runs/{name}/nodeRuns/{node_name}".format(
            name=name,
            node_name=node_name,
        ),
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[List["RunDict"]]:
    if response.status_code == HTTPStatus.OK:
        response_200 = []
        _response_200 = response.json()
        for componentsschemas_run_list_item_data in _response_200:
            componentsschemas_run_list_item = RunDict.from_dict(
                componentsschemas_run_list_item_data
            )

            response_200.append(componentsschemas_run_list_item)

        return response_200
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[List["RunDict"]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    name: str,
    node_name: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[List["RunDict"]]:
    """Get node runs info

    Args:
        name (str):
        node_name (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[List['RunDict']]
    """

    kwargs = _get_kwargs(
        name=name,
        node_name=node_name,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    name: str,
    node_name: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[List["RunDict"]]:
    """Get node runs info

    Args:
        name (str):
        node_name (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        List['RunDict']
    """

    return sync_detailed(
        name=name,
        node_name=node_name,
        client=client,
    ).parsed


async def asyncio_detailed(
    name: str,
    node_name: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[List["RunDict"]]:
    """Get node runs info

    Args:
        name (str):
        node_name (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[List['RunDict']]
    """

    kwargs = _get_kwargs(
        name=name,
        node_name=node_name,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    name: str,
    node_name: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[List["RunDict"]]:
    """Get node runs info

    Args:
        name (str):
        node_name (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        List['RunDict']
    """

    return (
        await asyncio_detailed(
            name=name,
            node_name=node_name,
            client=client,
        )
    ).parsed
