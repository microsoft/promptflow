import json
from functools import partial

from aiohttp import web

from promptflow.exceptions import ValidationException


def run_executor_server(port, has_error=False, init_error_file=None):
    app = web.Application()
    app.router.add_get("/health", _handle_health)

    handle_execution_with_customization = partial(_handle_execution, has_error=has_error)
    app.router.add_post("/execution", handle_execution_with_customization)

    print(f"Starting server on port {port}")
    if init_error_file is None:
        web.run_app(app, host="localhost", port=port)
    else:
        raise ValidationException("Error for tests")


async def _handle_health(request: web.Request):
    return web.Response(text="Healthy")


async def _handle_execution(request: web.Request, has_error=False):
    try:
        request = await request.json()
        return _get_execution_result(request, has_error=has_error)
    except json.JSONDecodeError:
        return web.Response(status=400, text="Bad Request: Invalid JSON")


def _get_execution_result(request: dict, has_error=False):
    run_id = request.get("run_id", "dummy_run_id")
    index = request.get("line_number", 1)
    inputs = request.get("inputs", {"question": "Hello world!"})

    if has_error and index == 1:
        # simulate error
        line_result_dict = _get_line_result_dict(run_id, index, inputs, has_error=True)
        return web.json_response(line_result_dict, status=500)

    line_result_dict = _get_line_result_dict(run_id, index, inputs)
    return web.json_response(line_result_dict)


def _get_line_result_dict(run_id, index, inputs, has_error=False):
    if has_error:
        return {
            "error": {
                "message": "error for tests",
                "messageFormat": "",
                "messageParameters": {},
                "referenceCode": None,
                "debugInfo": {
                    "type": "Exception",
                    "message": "error for tests",
                    "stackTrace": "...",
                    "innerException": None,
                },
                "additionalInfo": None,
                "code": "UserError",
                "innerError": {"code": "Exception", "innerError": None},
            },
        }
    return {
        "output": {"answer": "Hello world!"},
        "aggregation_inputs": {},
        "run_info": {
            "run_id": f"{run_id}_{index}",
            "status": "Completed",
            "inputs": inputs,
            "output": {"answer": "Hello world!"},
            "parent_run_id": run_id,
            "root_run_id": run_id,
            "start_time": "2023-11-24T06:03:20.2685529Z",
            "end_time": "2023-11-24T06:03:20.2688869Z",
            "index": index,
            "system_metrics": {"duration": "00:00:00.0003340", "total_tokens": 0},
            "result": {"answer": "Hello world!"},
        },
        "node_run_infos": {
            "get_answer": {
                "node": "get_answer",
                "flow_run_id": run_id,
                "parent_run_id": run_id,
                "run_id": "dummy_node_run_id",
                "status": "Completed",
                "inputs": inputs,
                "output": "Hello world!",
                "start_time": "2023-11-24T06:03:20.2688262Z",
                "end_time": "2023-11-24T06:03:20.268858Z",
                "index": index,
                "system_metrics": {"duration": "00:00:00.0000318", "total_tokens": 0},
                "result": "Hello world!",
            }
        },
    }


def _get_aggr_result_dict(run_id, inputs, has_error=False):
    if has_error:
        return {
            "error": {
                "message": "error for tests",
                "messageFormat": "",
                "messageParameters": {},
                "referenceCode": None,
                "debugInfo": {
                    "type": "Exception",
                    "message": "error for tests",
                    "stackTrace": "...",
                    "innerException": None,
                },
                "additionalInfo": None,
                "code": "UserError",
                "innerError": {"code": "Exception", "innerError": None},
            },
        }
    return {
        "output": None,
        "metrics": {"accuracy": 0.5},
        "node_run_infos": {
            "aggregation": {
                "node": "aggregation",
                "flow_run_id": run_id,
                "parent_run_id": run_id,
                "run_id": "dummy_node_run_id",
                "status": "Completed",
                "inputs": inputs,
                "output": "Hello world!",
                "start_time": "2023-11-24T06:03:20.2688262Z",
                "end_time": "2023-11-24T06:03:20.268858Z",
                "system_metrics": {"duration": "00:00:00.0000318", "total_tokens": 0},
                "result": "Hello world!",
            }
        },
    }
