import json

from aiohttp import web


def run_executor_server(port):
    app = web.Application()
    app.router.add_get("/health", _handle_health)
    app.router.add_post("/Execution", _handle_execution)

    print(f"Starting server on port {port}")
    web.run_app(app, host="localhost", port=port)


async def _handle_health(request: web.Request):
    return web.Response(text="Healthy")


async def _handle_execution(request: web.Request):
    try:
        request = await request.json()
        response_data = _get_line_result_dict(request)
        return web.json_response(response_data)
    except json.JSONDecodeError:
        return web.Response(status=400, text="Bad Request: Invalid JSON")


def _get_line_result_dict(request: dict):
    run_id = request.get("run_id", "dummy_run_id")
    index = request.get("line_number", 1)
    inputs = request.get("inputs", {"question": "Hello world!"})
    return {
        "output": {"answer": "Hello world!"},
        "aggregation_inputs": {},
        "run_info": {
            "run_id": run_id,
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
