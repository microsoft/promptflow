from http import HTTPStatus
from typing import Any, Dict, List, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.experiment_dict import ExperimentDict
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    max_results: Union[Unset, int] = UNSET,
    all_results: Union[Unset, bool] = False,
    archived_only: Union[Unset, bool] = False,
    include_archived: Union[Unset, bool] = False,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {}

    params["max_results"] = max_results

    params["all_results"] = all_results

    params["archived_only"] = archived_only

    params["include_archived"] = include_archived

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: Dict[str, Any] = {
        "method": "get",
        "url": "/Experiments/",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[List["ExperimentDict"]]:
    if response.status_code == HTTPStatus.OK:
        response_200 = []
        _response_200 = response.json()
        for componentsschemas_experiment_list_item_data in _response_200:
            componentsschemas_experiment_list_item = ExperimentDict.from_dict(
                componentsschemas_experiment_list_item_data
            )

            response_200.append(componentsschemas_experiment_list_item)

        return response_200
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[List["ExperimentDict"]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: Union[AuthenticatedClient, Client],
    max_results: Union[Unset, int] = UNSET,
    all_results: Union[Unset, bool] = False,
    archived_only: Union[Unset, bool] = False,
    include_archived: Union[Unset, bool] = False,
) -> Response[List["ExperimentDict"]]:
    """List all experiments

    Args:
        max_results (Union[Unset, int]):
        all_results (Union[Unset, bool]):  Default: False.
        archived_only (Union[Unset, bool]):  Default: False.
        include_archived (Union[Unset, bool]):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[List['ExperimentDict']]
    """

    kwargs = _get_kwargs(
        max_results=max_results,
        all_results=all_results,
        archived_only=archived_only,
        include_archived=include_archived,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: Union[AuthenticatedClient, Client],
    max_results: Union[Unset, int] = UNSET,
    all_results: Union[Unset, bool] = False,
    archived_only: Union[Unset, bool] = False,
    include_archived: Union[Unset, bool] = False,
) -> Optional[List["ExperimentDict"]]:
    """List all experiments

    Args:
        max_results (Union[Unset, int]):
        all_results (Union[Unset, bool]):  Default: False.
        archived_only (Union[Unset, bool]):  Default: False.
        include_archived (Union[Unset, bool]):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        List['ExperimentDict']
    """

    return sync_detailed(
        client=client,
        max_results=max_results,
        all_results=all_results,
        archived_only=archived_only,
        include_archived=include_archived,
    ).parsed


async def asyncio_detailed(
    *,
    client: Union[AuthenticatedClient, Client],
    max_results: Union[Unset, int] = UNSET,
    all_results: Union[Unset, bool] = False,
    archived_only: Union[Unset, bool] = False,
    include_archived: Union[Unset, bool] = False,
) -> Response[List["ExperimentDict"]]:
    """List all experiments

    Args:
        max_results (Union[Unset, int]):
        all_results (Union[Unset, bool]):  Default: False.
        archived_only (Union[Unset, bool]):  Default: False.
        include_archived (Union[Unset, bool]):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[List['ExperimentDict']]
    """

    kwargs = _get_kwargs(
        max_results=max_results,
        all_results=all_results,
        archived_only=archived_only,
        include_archived=include_archived,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: Union[AuthenticatedClient, Client],
    max_results: Union[Unset, int] = UNSET,
    all_results: Union[Unset, bool] = False,
    archived_only: Union[Unset, bool] = False,
    include_archived: Union[Unset, bool] = False,
) -> Optional[List["ExperimentDict"]]:
    """List all experiments

    Args:
        max_results (Union[Unset, int]):
        all_results (Union[Unset, bool]):  Default: False.
        archived_only (Union[Unset, bool]):  Default: False.
        include_archived (Union[Unset, bool]):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        List['ExperimentDict']
    """

    return (
        await asyncio_detailed(
            client=client,
            max_results=max_results,
            all_results=all_results,
            archived_only=archived_only,
            include_archived=include_archived,
        )
    ).parsed
