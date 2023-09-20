# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from collections.abc import Iterator


class IteratorProxy:
    """A proxy for iterator that can record all items that have been yielded from the generator."""

    def __init__(self, iterator: Iterator):
        self._iterator = iterator
        self._items = []

    def __iter__(self):
        return self

    def __next__(self):
        item = next(self._iterator)
        self._items.append(item)
        return item

    @property
    def items(self):
        return self._items


def generate_from_proxy(proxy: IteratorProxy):
    yield from proxy
