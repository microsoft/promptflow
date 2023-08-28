# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


class GeneratorProxy:
    """A proxy for generator that can record all items that have been yielded from the generator."""

    def __init__(self, generator):
        self._generator = generator
        self._items = []

    def __iter__(self):
        return self

    def __next__(self):
        item = next(self._generator)
        self._items.append(item)
        return item

    @property
    def items(self):
        return self._items


def generate_from_proxy(proxy: GeneratorProxy):
    yield from proxy
