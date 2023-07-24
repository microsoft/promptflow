# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import multiprocessing
import os
import pathlib
import signal
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request

from promptflow._constants import SYNC_REQUEST_TIMEOUT_THRESHOLD
from promptflow._version import VERSION
from promptflow.contracts.run_mode import RunMode
from promptflow.contracts.runtime import (
    BulkRunRequestV2,
    FlowRequestV2,
    MetaV2Request,
    SingleNodeRequestV2,
    SubmitFlowRequest,
)
from promptflow.contracts.tool import ToolType
from promptflow.core import RunTracker
from promptflow.core.operation_context import OperationContext
from promptflow.exceptions import RESPONSE_CODE, ErrorResponse, ExceptionPresenter, JsonSerializedPromptflowException
from promptflow.utils.generate_tool_meta_utils import generate_prompt_meta, generate_python_meta
from promptflow.utils.run_result_parser import RunResultParser
from promptflow.utils.utils import get_runtime_version

from .error_codes import (
    GenerateMetaTimeout,
    MetaFileNotFound,
    MetaFileReadError,
    NoToolTypeDefined,
    RuntimeTerminatedByUser,
)
from .runtime import (
    PromptFlowRuntime,
    execute_bulk_run_request,
    execute_flow_request,
    execute_node_request,
    get_log_context,
    get_log_context_from_v2_request,
)
from .runtime_config import load_runtime_config
from .utils import logger, multi_processing_exception_wrapper, setup_contextvar
from .utils._flow_source_helper import fill_working_dir

app = Flask(__name__)

active_flow_request_context = ContextVar("SubmitFlowRequest", default=None)


def signal_handler(signum, frame):
    signame = signal.Signals(signum).name
    logger.info("Runtime stopping. Handling signal %s (%s)", signame, signum)
    try:
        flow_request: SubmitFlowRequest = active_flow_request_context.get()
        run_tracker = RunTracker.active_instance()
        if flow_request is not None and run_tracker is not None:
            flow_id = flow_request.flow_id
            all_run_ids = flow_request.get_root_run_ids()
            logger.info("Update flow runs to failed on exit. Flow id: %s, root run ids: %s", flow_id, all_run_ids)
            ex = RuntimeTerminatedByUser(
                f"Flow run failed because runtime is terminated at {datetime.utcnow().isoformat()}. "
                f"It may be caused by runtime version update or compute instance stop."
            )
            # Update active runs to failed first, then not started runs.
            # Because mark_notstarted_runs_as_failed may start new run, we may meet mlflow error
            # "To start a new run, first end the current run with mlflow.end_run()." if there's active run.
            run_tracker.mark_active_runs_as_failed_on_exit(root_run_ids=all_run_ids, ex=ex)
            run_tracker.mark_notstarted_runs_as_failed(flow_id=flow_id, root_run_ids=all_run_ids, ex=ex)
    except Exception:
        logger.warning("Error when handling runtime stop signal", exc_info=True)
    finally:
        sys.exit(1)


# register signal handler to gracefully shutdown
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


@app.errorhandler(Exception)
def handle_exception(e):
    """Return JSON instead of HTML for HTTP errors with correct error code & error category."""

    resp = generate_error_response(e)

    return jsonify(resp.to_dict()), resp.response_code


def generate_error_response(e):
    if isinstance(e, JsonSerializedPromptflowException):
        error_dict = json.loads(e.message)
    else:
        error_dict = ExceptionPresenter(e).to_dict(include_debug_info=True)
    logger.warning(
        "Hit exception when execute request: \n{customer_content}", extra={"customer_content": str(error_dict)}
    )

    # remove traceback from response
    config = PromptFlowRuntime.get_instance().config
    if config.execution.debug is False:
        error_dict.pop("debugInfo", None)

    return ErrorResponse.from_error_dict(error_dict)


def set_operation_context(request, run_mode):
    # Get the request id from the headers
    req_id = request.headers.get("x-ms-client-request-id") or request.headers.get("x-request-id")

    # Get the user agent from the headers and append the runtime version
    user_agent = request.headers.get("User-Agent", "")
    runtime_user_agent = " ".join(
        (
            f"promptflow-runtime/{get_runtime_version()}",
            user_agent,
        )
    )

    # Get the operation context instance and set its attributes
    operation_context = OperationContext.get_instance()
    operation_context.user_agent = runtime_user_agent
    operation_context.request_id = req_id
    operation_context.run_mode = run_mode.name if run_mode is not None else ""

    # Return the operation context object
    return operation_context


@app.route("/submit_single_node", methods=["POST"])
@app.route("/aml-api/v1.0/submit_single_node", methods=["POST"])
def submit_single_node():
    """Process a single node request in the runtime."""
    runtime: PromptFlowRuntime = PromptFlowRuntime.get_instance()
    req = SingleNodeRequestV2.deserialize(request.get_json())
    req_id = request.headers.get("x-ms-client-request-id")
    operation_context = set_operation_context(request, RunMode.SingleNode)
    with get_log_context_from_v2_request(
        req,
        runtime.config.deployment.edition,
        custom_dimensions=operation_context.get_context_dict()
    ):
        # Please do not change it, it is used to generate dashboard.
        logger.info(
            "[%s] Receiving v2 single node request %s: {customer_content}",
            req.flow_run_id,
            req_id,
            extra={"customer_content": req.desensitize_to_json()},
        )

        try:
            result = runtime.execute_flow(req, execute_node_request)
            logger.info("[%s] End processing single node", req.flow_run_id)

            return generate_response_from_run_result(result, req.flow_run_id)
        except Exception as ex:
            _log_submit_request_error_response(ex)
            raise ex


@app.route("/submit_flow", methods=["POST"])
@app.route("/aml-api/v1.0/submit_flow", methods=["POST"])
def submit_flow():
    runtime: PromptFlowRuntime = PromptFlowRuntime.get_instance()
    req = FlowRequestV2.deserialize(request.get_json())
    req_id = request.headers.get("x-ms-client-request-id")
    operation_context = set_operation_context(request, RunMode.Flow)
    with get_log_context_from_v2_request(
        req,
        runtime.config.deployment.edition,
        custom_dimensions=operation_context.get_context_dict()
    ):
        # Please do not change it, it is used to generate dashboard.
        logger.info(
            "[%s] Receiving v2 flow request %s: {customer_content}",
            req.flow_run_id,
            req_id,
            extra={"customer_content": req.desensitize_to_json()},
        )

        try:
            result = runtime.execute_flow(req, execute_flow_request)
            logger.info("[%s] End processing flow", req.flow_run_id)

            return generate_response_from_run_result(result, req.flow_run_id)
        except Exception as ex:
            _log_submit_request_error_response(ex)
            raise ex


@app.route("/submit_bulk_run", methods=["POST"])
@app.route("/aml-api/v1.0/submit_bulk_run", methods=["POST"])
def submit_bulk_run():
    runtime: PromptFlowRuntime = PromptFlowRuntime.get_instance()
    req = BulkRunRequestV2.deserialize(request.get_json())
    req_id = request.headers.get("x-ms-client-request-id")
    operation_context = set_operation_context(request, RunMode.BulkTest)
    with get_log_context_from_v2_request(
        req,
        runtime.config.deployment.edition,
        custom_dimensions=operation_context.get_context_dict()
    ):
        # Please do not change it, it is used to generate dashboard.
        logger.info(
            "[%s] Receiving v2 bulk run request %s: {customer_content}",
            req.flow_run_id,
            req_id,
            extra={"customer_content": req.desensitize_to_json()},
        )

        try:
            result = runtime.execute_flow(req, execute_bulk_run_request)
            logger.info("[%s] End processing bulk run", req.flow_run_id)
            return generate_response_from_run_result(result, req.flow_run_id)
        except Exception as ex:
            _log_submit_request_error_response(ex)
            raise ex


def generate_response_from_run_result(result: dict, run_id):
    error_response = RunResultParser(result).get_error_response()
    if error_response:
        result["errorResponse"] = error_response

    resp = jsonify(result)

    return resp


@app.route("/score", methods=["POST"])
@app.route("/submit", methods=["POST"])
@app.route("/aml-api/v1.0/score", methods=["POST"])
@app.route("/aml-api/v1.0/submit", methods=["POST"])
def submit():
    """process a flow request in the runtime."""
    result = {}
    payload = request.get_json()
    user_agent = request.headers.get("User-Agent", "")
    req_id = request.headers.get("x-ms-client-request-id")
    if not req_id:
        req_id = request.headers.get("x-request-id")
    runtime: PromptFlowRuntime = PromptFlowRuntime.get_instance()
    flow_request = None
    try:
        flow_request = SubmitFlowRequest.deserialize(payload)
        runtime_user_agent = " ".join(
            (
                f"promptflow-runtime/{get_runtime_version()}",
                user_agent,
            )
        )
        operation_context = OperationContext.get_instance()
        operation_context.user_agent = runtime_user_agent
        operation_context.request_id = req_id
        operation_context.run_mode = flow_request.run_mode.name if flow_request.run_mode is not None else ""

        log_context = get_log_context(
            flow_request, runtime.config.deployment.edition, custom_dimensions=operation_context.get_context_dict())
        with log_context, setup_contextvar(
            active_flow_request_context, flow_request
        ):
            # Please do not change it, it is used to generate dashboard.
            logger.info(
                "[%s] Receiving submit flow request %s: {customer_content}",
                flow_request.flow_run_id,
                req_id,
                extra={"customer_content": SubmitFlowRequest.desensitize_to_json(flow_request)},
            )
            try:
                result = runtime.execute(flow_request)
                logger.info("[%s] End processing flow", flow_request.flow_run_id)
                # diagnostic: dump the response to a local file
                if runtime.config.execution.debug:
                    with open("output.json", "w", encoding="utf-8") as file:
                        json.dump(result, file, indent=2)

                return generate_response_from_run_result(result, flow_request.flow_run_id)
            except Exception as ex:
                _log_submit_request_error_response(ex)
                raise ex
    except Exception as ex:
        runtime.mark_flow_runs_as_failed(flow_request, payload, ex)
        raise ex


@app.route("/aml-api/v1.0/package_tools")
@app.route("/package_tools")
def package_tools():
    import imp

    import pkg_resources

    imp.reload(pkg_resources)
    from promptflow.core.tools_manager import collect_package_tools

    return jsonify(collect_package_tools())


@app.route("/aml-api/v1.0/meta", methods=["POST"])
@app.route("/meta", methods=["POST"])
def meta():
    # Get parameters and payload
    tool_type = request.args.get("tool_type", type=str)
    name = request.args.get("name", type=str)
    payload = request.get_data(as_text=True)
    logger.info(
        "Receiving meta request: name=%s tool_type=%s payload={customer_content}",
        name,
        tool_type,
        extra={"customer_content": payload},
    )

    manager = multiprocessing.Manager()
    return_dict = manager.dict()
    exception_queue = multiprocessing.Queue()
    p = multiprocessing.Process(
        target=generate_meta_multiprocessing, args=(payload, name, tool_type, return_dict, exception_queue)
    )
    p.start()
    p.join()
    # when p is killed by signal, exitcode will be negative without exception
    if p.exitcode and p.exitcode > 0:
        exception = None
        try:
            exception = exception_queue.get(timeout=SYNC_REQUEST_TIMEOUT_THRESHOLD)
        except Exception:
            pass
        # JsonSerializedPromptflowException will be raised here
        # no need to change to PromptflowException since it will be handled in app.handle_exception
        # we can unify the exception when we decide to expose executor.execute as an public API
        if exception is not None:
            raise exception
    result = return_dict.get("result", {})

    logger.info("Result: %s", result)
    logger.info("Child process finished!")

    resp = jsonify(result)

    if isinstance(result, dict) and RESPONSE_CODE in result:
        resp.status_code = result[RESPONSE_CODE]

    return resp


# S2S calls for CI need prefix "/aml-api/v1.0"
@app.route("/aml-api/v1.0/meta-v2/", methods=["POST"])
@app.route("/meta-v2", methods=["POST"])
def meta_v2():
    # Get parameters and payload
    logger.info("Receiving v2 meta request: payload = {customer_content}", extra={"customer_content": request.json})
    data = MetaV2Request.deserialize(request.json)
    runtime: PromptFlowRuntime = PromptFlowRuntime.get_instance()
    runtime_dir = fill_working_dir(
        runtime.config.deployment.compute_type, data.flow_source_info, "meta_%s" % uuid.uuid4()
    )
    logger.info("Generate meta_v2 in runtime_dir {customer_content}", extra={"customer_content": runtime_dir})
    manager = multiprocessing.Manager()
    tool_dict = manager.dict()
    exception_dict = manager.dict()
    p = multiprocessing.Process(
        target=generate_metas_from_files, args=(data.tools, runtime_dir, tool_dict, exception_dict)
    )
    p.start()
    p.join(timeout=SYNC_REQUEST_TIMEOUT_THRESHOLD)
    if p.is_alive():
        logger.info(f"Stop generating meta for exceeding {SYNC_REQUEST_TIMEOUT_THRESHOLD} seconds.")
        p.terminate()
        p.join()

    resp_tools = {source: json.loads(tool) for source, tool in tool_dict.items()}
    # exception_dict was created by manager.dict(), so convert to a normal dict here.
    resp_errors = {source: exception for source, exception in exception_dict.items()}
    # For not processed tools, treat as timeout error.
    for source in data.tools.keys():
        if source not in resp_tools and source not in resp_errors:
            resp_errors[source] = generate_error_response(
                GenerateMetaTimeout(message_format="Generate meta timeout for source '{source}'.", source=source)
            ).to_dict()
    resp = {"tools": resp_tools, "errors": resp_errors}
    return jsonify(resp)


def generate_metas_from_files(tools, runtime_dir, tool_dict, exception_dict):
    sys.path.insert(0, str(runtime_dir))
    for source, config in tools.items():
        try:
            if "tool_type" not in config:
                raise NoToolTypeDefined(message_format="Tool type not defined for source '{source}'.", source=source)
            tool_type = config.get("tool_type")
            file_path = pathlib.Path(runtime_dir, source)
            logger.info(f"Start to generate meta, file path = '{file_path}', type = {tool_type}.")

            if not file_path.exists():
                logger.error(f"Skip generating meta for file not found, file path '{file_path}', type '{tool_type}'.")
                raise MetaFileNotFound(
                    message_format="Meta file not found, path '{file_path}', type '{tool_type}'.",
                    file_path=str(file_path),
                    tool_type=tool_type,
                )
            try:
                content = file_path.read_text()
            except Exception as e:
                logger.error(
                    "Skip generating meta for reading file failed. "
                    + f"Path '{file_path}', type '{tool_type}', exception {e}."
                )
                raise MetaFileReadError(
                    message_format=(
                        "Reading meta file failed, path '{file_path}', type '{tool_type}', exception {exception}."
                    ),
                    file_path=str(file_path),
                    tool_type=tool_type,
                    exception=str(e),
                ) from e

            if tool_type == ToolType.LLM:
                result = generate_prompt_meta(source, content, source=source)
            elif tool_type == ToolType.PROMPT:
                result = generate_prompt_meta(source, content, prompt_only=True, source=source)
            else:
                result = generate_python_meta(source, content, source=source)

            tool_dict[source] = result
        except Exception as e:
            exception_dict[source] = generate_error_response(e).to_dict()


@app.route("/aml-api/v1.0/health", methods=["GET"])
@app.route("/health", methods=["GET"])
def health():
    """Check if the runtime is alive."""
    return {"status": "Healthy", "version": VERSION}


@app.route("/aml-api/v1.0/version", methods=["GET"])
@app.route("/version", methods=["GET"])
def version():
    """Check the runtime's version."""
    build_info = os.environ.get("BUILD_INFO", "")
    try:
        build_info_dict = json.loads(build_info)
        version = build_info_dict["build_number"]
    except Exception:
        version = VERSION
    return {"status": "Healthy", "build_info": build_info, "version": version}


def generate_meta_multiprocessing(content, name, tool_type, return_dict, exception_queue):
    """Generate meta data unbder isolated process.
    Note: do not change order of params since it will be used in multiprocessing executor.
    """
    with multi_processing_exception_wrapper(exception_queue):
        if tool_type == ToolType.LLM:
            result = generate_prompt_meta(name, content)
        elif tool_type == ToolType.PROMPT:
            result = generate_prompt_meta(name, content, prompt_only=True)
        else:
            result = generate_python_meta(name, content)
        return_dict["result"] = result


def create_app(config="prt.yaml", args=None):
    """Create a flask app."""
    config = Path(config).absolute()
    logger.info("Init runtime with config file in create_app: %s", config)
    config = load_runtime_config(config, args=args)
    PromptFlowRuntime.init(config)
    logger.info("Finished init runtime with config file in create_app.")
    PromptFlowRuntime.get_instance().init_storage()
    logger.info("Finished init storage in create_app.")
    PromptFlowRuntime.get_instance().init_operation_context()
    logger.info("Finished init operation context in create_app.")
    return app


def _log_submit_request_error_response(ex):
    resp: ErrorResponse = generate_error_response(ex)
    # Please do not change it, it is used to generate dashboard.
    logger.error(
        (
            "Submit flow request failed "
            f"Code: {resp.response_code} "
            f"Exception type: {type(ex)} "
            f"InnerException type: {resp.innermost_error_code} "
            f"Exception type hierarchy: {resp.error_code_hierarchy}"
        )
    )


if __name__ == "__main__":
    PromptFlowRuntime.get_instance().init_logger()
    app.run()
