# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Any, AsyncIterator, Iterator

from .context_manager_proxy import ContextManagerProxy


class IteratorProxy(ContextManagerProxy):
    """A proxy for an iterator that can record all items that have been yielded."""

    def __init__(self, iterator: Iterator[Any]):
        self._iterator = iterator
        self._items = []
        super().__init__(iterator)

    def __iter__(self):
        return self

    def __next__(self):
        item = next(self._iterator)
        self._items.append(item)
        return item

    @property
    def items(self) -> list:
        """
        Get all items that have been yielded from the iterator.

        :return: A list of yielded items.
        """
        return self._items


class AsyncIteratorProxy(ContextManagerProxy):
    """A proxy for an async iterator that can record all items that have been yielded."""

    def __init__(self, iterator: AsyncIterator[Any]):
        """
        Initialize the AsyncIteratorProxy with an async iterator.

        :param iterator: An async iterator to proxy.
        """
        self._iterator = iterator
        self._items = []
        super().__init__(iterator)

    def __aiter__(self):
        return self

    async def __anext__(self):
        item = await self._iterator.__anext__()
        self._items.append(item)
        return item

    @property
    def items(self) -> list:
        """
        Get all items that have been yielded from the iterator.

        :return: A list of yielded items.
        """
        return self._items
