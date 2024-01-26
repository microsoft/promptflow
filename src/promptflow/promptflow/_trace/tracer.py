# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


class Tracer:
    def trace(span) -> None:
        ...


def _get_tracer() -> Tracer:
    # return the global singleton tracer
    ...
