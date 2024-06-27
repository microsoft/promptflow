import json
import shutil
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlencode, urlunparse

from promptflow._constants import FlowLanguage
from promptflow._sdk._constants import DEFAULT_ENCODING, PROMPT_FLOW_DIR_NAME, UX_INPUTS_INIT_KEY, UX_INPUTS_JSON
from promptflow._sdk._service.utils.utils import encrypt_flow_path
from promptflow._sdk._utilities.general_utils import (
    _get_additional_includes,
    generate_yaml_entry_without_delete,
    resolve_flow_language,
)
from promptflow._sdk._utilities.monitor_utils import (
    DirectoryModificationMonitorTarget,
    FileModificationMonitorTarget,
    JsonContentMonitorTarget,
    Monitor,
)
from promptflow._sdk._utilities.serve_utils import CSharpServeAppHelper, PythonServeAppHelper, ServeAppHelper
from promptflow._utils.flow_utils import resolve_flow_path


def print_log(text):
    print(text)


def construct_flow_absolute_path(flow: str) -> str:
    flow_dir, flow_file = resolve_flow_path(flow)
    return (flow_dir / flow_file).absolute().resolve().as_posix()


# Todo: use base64 encode for now, will consider whether need use encryption or use db to store flow path info
def construct_chat_page_url(flow_path, port, service_host, url_params):
    encrypted_flow_path = encrypt_flow_path(flow_path)
    query_dict = {"flow": encrypted_flow_path, **url_params}
    query_params = urlencode(query_dict)
    return urlunparse(("http", f"{service_host}:{port}", "/v1.0/ui/chat", "", query_params, ""))


def _try_restart_service(
    *,
    last_result: ServeAppHelper,
    flow_file_path: Path,
    flow_dir: Path,
    serve_app_port: int,
    ux_input_path: Path,
    environment_variables: Dict[str, str],
    chat_page_url: str,
    skip_open_browser: bool,
):
    if last_result is not None:
        last_helper, skip_open_browser = last_result
        print_log("Changes detected, stopping current serve app...")
        last_helper.terminate()

    # init must be always loaded from ux_inputs.json
    if not ux_input_path.is_file():
        init = {}
    else:
        ux_inputs = json.loads(ux_input_path.read_text(encoding=DEFAULT_ENCODING))
        init = ux_inputs.get(UX_INPUTS_INIT_KEY, {}).get(flow_file_path.name, {})

    language = resolve_flow_language(flow_path=flow_file_path, working_dir=flow_dir)
    if language == FlowLanguage.Python:
        # additional includes will always be called by the helper.
        # This is expected as user will change files in original locations only
        helper = PythonServeAppHelper(
            flow_file_path=flow_file_path,
            flow_dir=flow_dir,
            init=init,
            port=serve_app_port,
            environment_variables=environment_variables,
            chat_page_url=chat_page_url,
        )
    else:
        helper = CSharpServeAppHelper(
            flow_file_path=flow_file_path,
            flow_dir=flow_dir,
            init=init,
            port=serve_app_port,
            environment_variables=environment_variables,
            chat_page_url=chat_page_url,
        )

    print_log("Starting serve app...")
    try:
        helper.start(skip_open_browser=skip_open_browser)
        # only open on first successful start
        skip_open_browser = True
    except Exception:
        print_log("Failed to start serve app, please check the error message above.")
    finally:
        return helper, skip_open_browser


def update_init_in_ux_inputs(*, ux_input_path: Path, flow_file_name: str, init: Dict[str, Any]):
    # ensure that ux_inputs.json is created or updated so that we can always load init from it in monitor
    if not ux_input_path.is_file():
        ux_input_path.parent.mkdir(exist_ok=True, parents=True)
        ux_input_path.write_text(json.dumps({UX_INPUTS_INIT_KEY: {flow_file_name: init}}, indent=4, ensure_ascii=False))
        return

    # avoid updating init if it's not provided
    if not init:
        return

    # update init to ux_inputs.json
    current_ux_inputs = json.loads(ux_input_path.read_text(encoding=DEFAULT_ENCODING))
    if UX_INPUTS_INIT_KEY not in current_ux_inputs:
        current_ux_inputs[UX_INPUTS_INIT_KEY] = {}
    # save init with different key given there can be multiple prompty flow in one directory
    current_ux_inputs[UX_INPUTS_INIT_KEY][flow_file_name] = init
    ux_input_path.parent.mkdir(exist_ok=True, parents=True)
    ux_input_path.write_text(json.dumps(current_ux_inputs, indent=4, ensure_ascii=False), encoding="utf-8")


touch_iter_count = 0


def touch_local_pfs():
    from promptflow._sdk._tracing import _invoke_pf_svc

    global touch_iter_count

    touch_iter_count += 1
    # invoke every 20-30 minutes for now, so trigger every 12000
    # iterations given 1 iteration takes around 0.1s if no change
    if touch_iter_count % 12000 == 0:
        _invoke_pf_svc()


def start_chat_ui_service_monitor(
    flow: str,
    *,
    serve_app_port: str,
    pfs_port: str,
    service_host: str,
    url_params: Dict[str, str],
    init: Dict[str, Any],
    enable_internal_features: bool = False,
    skip_open_browser: bool = False,
    environment_variables: Dict[str, str] = None,
):
    # if flow is an entry, generate yaml entry without delete; if flow is a path, use it directly
    flow_file_path = generate_yaml_entry_without_delete(entry=flow)
    use_entry_as_flow = flow_file_path != flow
    if use_entry_as_flow:
        flow_dir = Path(".")
        flow_file_name = flow_file_path.name
        # when using entry as flow, chat UI will now access ux_inputs.json and images in temp directory
        ux_input_path = flow_file_path.parent / PROMPT_FLOW_DIR_NAME / UX_INPUTS_JSON

        # so we need to copy the original ux_inputs.json to temp directory
        origin_prompt_flow_dir = flow_dir / PROMPT_FLOW_DIR_NAME
        if origin_prompt_flow_dir.is_dir():
            # TODO: skip files that no need to copy, like logs for flow run
            shutil.copytree(origin_prompt_flow_dir, flow_file_path.parent / PROMPT_FLOW_DIR_NAME)
    else:
        flow_dir, flow_file_name = resolve_flow_path(flow, allow_prompty_dir=True)
        flow_file_path = flow_dir / flow_file_name
        ux_input_path = flow_dir / PROMPT_FLOW_DIR_NAME / UX_INPUTS_JSON
        origin_prompt_flow_dir = None

    update_init_in_ux_inputs(ux_input_path=ux_input_path, flow_file_name=flow_file_name, init=init)

    # show url for chat UI
    url_params["serve_app_port"] = serve_app_port
    if "enable_internal_features" not in url_params:
        # /eval is not supported in chat window when using entry as a flow for now
        url_params["enable_internal_features"] = (
            "true" if enable_internal_features and not use_entry_as_flow else "false"
        )
    chat_page_url = construct_chat_page_url(
        # Chat UI now doesn't support as_posix in windows
        str(flow_file_path),
        pfs_port,
        service_host,
        url_params=url_params,
    )

    targets = [
        DirectoryModificationMonitorTarget(
            target=flow_dir,
            relative_root_ignores=[PROMPT_FLOW_DIR_NAME, "__pycache__"],
        ),
        JsonContentMonitorTarget(
            target=ux_input_path,
            node_path=[UX_INPUTS_INIT_KEY, flow_file_name],
        ),
    ]

    for additional_includes in _get_additional_includes(flow_file_path):
        target = Path(additional_includes)
        if target.is_file():
            targets.append(
                FileModificationMonitorTarget(
                    target=target,
                )
            )
        elif target.is_dir():
            targets.append(
                DirectoryModificationMonitorTarget(
                    target=target,
                    relative_root_ignores=["__pycache__"],
                )
            )

    print_log(f"Chat page URL will be available after service is started: {chat_page_url}")

    monitor = Monitor(
        targets=targets,
        target_callback=_try_restart_service,
        target_callback_kwargs={
            "flow_file_path": flow_file_path,
            "flow_dir": flow_dir,
            "serve_app_port": int(serve_app_port),
            "ux_input_path": ux_input_path,
            "environment_variables": environment_variables,
            "chat_page_url": chat_page_url,
            "skip_open_browser": skip_open_browser,
        },
        inject_last_callback_result=True,
        extra_logic_in_loop=touch_local_pfs,
    )

    try:
        monitor.start_monitor()
    except KeyboardInterrupt:
        print_log("Stopping monitor and attached serve app...")
        if monitor.last_callback_result is not None:
            serve_app_helper, _ = monitor.last_callback_result
            serve_app_helper.terminate()
        print_log("Stopped monitor and attached serve app.")
    finally:
        if use_entry_as_flow:
            shutil.copytree(flow_file_path.parent / PROMPT_FLOW_DIR_NAME, origin_prompt_flow_dir, dirs_exist_ok=True)
