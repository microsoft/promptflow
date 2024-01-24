import logging
import threading
import uuid

from sqlalchemy.exc import OperationalError

from model import Span
from utils import generate_a_span, sqlite_timer


def setup_logger() -> None:
    for name in ["sqlite.timer", "span.persisting"]:
        logging.getLogger(name).setLevel(logging.INFO)
        file_handler = logging.FileHandler(f"{name}.log")
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logging.getLogger(name).addHandler(file_handler)


@sqlite_timer("persist_span")
def retriable_span_persist(span: Span) -> None:
    while True:
        try:
            span.persist()
            return
        except OperationalError:
            # warn this, then we can collect how many times we run into databse lock
            logging.getLogger("span.persisting").warning(f"retrying persisting span[{id(span)}]...")


def mock_span_collector(span: Span) -> None:
    # this is the mock function that how PFS collect spans
    # open a new thread to persist the span
    thread = threading.Thread(target=retriable_span_persist, args=(span,))
    thread.start()


def write_perf_multithread() -> None:
    # according to our design, there will be 10 spans per line
    # so we need 10K lines to make 100K spans
    # one line means same `trace_id`
    # following this to generate such a database
    for _ in range(10000):
        trace_id = str(uuid.uuid4())
        parent_span = generate_a_span(trace_id=trace_id)
        parent_span_id = parent_span.span_id
        mock_span_collector(parent_span)
        for _ in range(10):
            sub_span = generate_a_span(trace_id=trace_id, parent_id=parent_span_id)
            mock_span_collector(sub_span)


def main():
    setup_logger()
    write_perf_multithread()


if __name__ == "__main__":
    main()
