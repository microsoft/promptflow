import uuid

from utils import generate_a_span


def prepare_100k_db() -> None:
    # according to our design, there will be 10 spans per line
    # so we need 10K lines to make 100K spans
    # one line means same `trace_id`
    # following this to generate such a database
    for _ in range(10000):
        trace_id = str(uuid.uuid4())
        parent_span = generate_a_span(trace_id=trace_id)
        parent_span_id = parent_span.span_id
        parent_span.persist()
        for _ in range(10):
            sub_span = generate_a_span(trace_id=trace_id, parent_id=parent_span_id)
            sub_span.persist()


if __name__ == "__main__":
    prepare_100k_db()
