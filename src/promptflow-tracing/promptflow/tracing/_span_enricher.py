from typing import Dict

from .contracts.trace import TraceType


class SpanEnricher:
    def __init__(self):
        pass

    def enrich(self, span, inputs, output):
        """This method is used to enrich the span with the inputs and output of the traced function.
        Note that this method is called after the function is called, so some inputs related logic is not here.
        """
        #  TODO: Also move input related logic here.
        from ._trace import enrich_span_with_output

        enrich_span_with_output(span, output)


class SpanEnricherManager:
    _instance = None

    def __init__(self):
        self._type2enricher: Dict[str, SpanEnricher] = {}
        self._base_enricher = SpanEnricher()

    @classmethod
    def get_instance(cls) -> "SpanEnricherManager":
        if cls._instance is None:
            cls._instance = SpanEnricherManager()
        return cls._instance

    @classmethod
    def register(cls, trace_type, enricher: SpanEnricher):
        cls.get_instance()._register(trace_type, enricher)

    @classmethod
    def enrich(cls, span, inputs, output, trace_type):
        cls.get_instance()._enrich(span, inputs, output, trace_type)

    def _register(self, trace_type, enricher: SpanEnricher):
        self._type2enricher[trace_type] = enricher

    def _enrich(self, span, inputs, output, trace_type):
        enricher = self._type2enricher.get(trace_type, self._base_enricher)
        enricher.enrich(span, inputs, output)


SpanEnricherManager.register(TraceType.FUNCTION, SpanEnricher())
