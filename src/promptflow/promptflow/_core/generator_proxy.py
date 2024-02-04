# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow._core.otel_tracer import get_otel_tracer


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


tracer = get_otel_tracer("promptflow")


class TracedGeneratorProxy(GeneratorProxy):
    def __init__(self, generator, span_context):
        super().__init__(generator)
        self._span_context = span_context

    def __next__(self):
        with tracer.start_as_current_span(self._name):
            return super().__next__()


def generate_from_proxy(proxy: GeneratorProxy):
    print("generate_from_proxy start")
    with tracer.start_as_current_span("generate_from_proxy"):
        yield from proxy
    print("generate_from_proxy end")
