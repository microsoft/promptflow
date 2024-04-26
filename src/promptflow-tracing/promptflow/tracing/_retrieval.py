import json
from typing import Callable

from opentelemetry.trace import Span

from ._span_enricher import SpanEnricher, SpanEnricherManager
from ._trace import TraceType, _traced

keys = ["id", "score", "content", "metadata"]


class RetrievalSpanEnricher(SpanEnricher):
    def enrich(self, span: Span, inputs, output: list):
        super().enrich(span, inputs, output)
        if "query" in inputs:
            query = inputs["query"]
            span.set_attribute("retrieval.query", query)
        if not isinstance(output, list):
            return
        docs = []

        # It's tricky here when switching index from one to another
        for doc in output:
            if not isinstance(doc, dict):
                continue
            item = {}
            for key in keys:
                if key in doc:
                    item["document." + key] = doc[key]
            if item:
                docs.append(item)
        if docs:
            span.add_event("promptflow.retrieval.documents", {"payload": json.dumps(docs)})


SpanEnricherManager.register(TraceType.RETRIEVAL, RetrievalSpanEnricher())


def retrieval(
    func: Callable,
) -> Callable:
    """Use @retrieval to define retrieval spans.
    For example:
    @retrieval
    def my_retrieval_func(query: str) -> List[Dict[str, Any]]:
        return [{"id": "1", "score": 0.9, "content": "content", "metadata": {}}]

    Note:
    One keyword argument "query" is required for the function, it is shown as the retrieval query in the trace.
    The return value should be a list of dictionaries, each dictionary represents a document with the following keys:
    - content: The content of the document.
    - id(Optional): The unique identifier of the document.
    - score(Optional): The relevance score of the document.
    - metadata(Optional): Other metadata of the document.
    """
    return _traced(func, trace_type=TraceType.RETRIEVAL)
