from http import HTTPStatus
from typing import Any, Dict, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.experiment_dict import ExperimentDict
from ...types import UNSET, Response, Unset


def _get_kwargs(
    name: str,
    *,
    from_nodes: Union[Unset, str] = UNSET,
    nodes: Union[Unset, str] = UNSET,
    executable_path: Union[Unset, str] = UNSET,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {}

    params["from_nodes"] = from_nodes

    params["nodes"] = nodes

    params["executable_path"] = executable_path

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: Dict[str, Any] = {
        "method": "post",
        "url": "/Experiments/{name}/start".format(
            name=name,
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[ExperimentDict]:
    if response.status_code == HTTPStatus.OK:
        response_200 = ExperimentDict.from_dict(response.json())

        return response_200
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[ExperimentDict]:
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
    from_nodes: Union[Unset, str] = UNSET,
    nodes: Union[Unset, str] = UNSET,
    executable_path: Union[Unset, str] = UNSET,
) -> Response[ExperimentDict]:
    """Start experiment

    Args:
        name (str):
        from_nodes (Union[Unset, str]):
        nodes (Union[Unset, str]):
        executable_path (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ExperimentDict]
    """

    kwargs = _get_kwargs(
        name=name,
        from_nodes=from_nodes,
        nodes=nodes,
        executable_path=executable_path,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    name: str,
    *,
    client: Union[AuthenticatedClient, Client],
    from_nodes: Union[Unset, str] = UNSET,
    nodes: Union[Unset, str] = UNSET,
    executable_path: Union[Unset, str] = UNSET,
) -> Optional[ExperimentDict]:
    """Start experiment

    Args:
        name (str):
        from_nodes (Union[Unset, str]):
        nodes (Union[Unset, str]):
        executable_path (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ExperimentDict
    """

    return sync_detailed(
        name=name,
        client=client,
        from_nodes=from_nodes,
        nodes=nodes,
        executable_path=executable_path,
    ).parsed


async def asyncio_detailed(
    name: str,
    *,
    client: Union[AuthenticatedClient, Client],
    from_nodes: Union[Unset, str] = UNSET,
    nodes: Union[Unset, str] = UNSET,
    executable_path: Union[Unset, str] = UNSET,
) -> Response[ExperimentDict]:
    """Start experiment

    Args:
        name (str):
        from_nodes (Union[Unset, str]):
        nodes (Union[Unset, str]):
        executable_path (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ExperimentDict]
    """

    kwargs = _get_kwargs(
        name=name,
        from_nodes=from_nodes,
        nodes=nodes,
        executable_path=executable_path,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    name: str,
    *,
    client: Union[AuthenticatedClient, Client],
    from_nodes: Union[Unset, str] = UNSET,
    nodes: Union[Unset, str] = UNSET,
    executable_path: Union[Unset, str] = UNSET,
) -> Optional[ExperimentDict]:
    """Start experiment

    Args:
        name (str):
        from_nodes (Union[Unset, str]):
        nodes (Union[Unset, str]):
        executable_path (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ExperimentDict
    """

    return (
        await asyncio_detailed(
            name=name,
            client=client,
            from_nodes=from_nodes,
            nodes=nodes,
            executable_path=executable_path,
        )
    ).parsed
