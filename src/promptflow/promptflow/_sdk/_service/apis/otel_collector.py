# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json

from flask import request


def trace_collector():
    trace_data = request.data
    trace = json.loads(trace_data)
    print(trace)

    return "Traces received", 200
