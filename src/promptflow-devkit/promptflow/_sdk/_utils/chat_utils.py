from pathlib import Path
from urllib.parse import urlencode, urlunparse

from promptflow._utils.flow_utils import resolve_flow_path


def construct_flow_absolute_path(flow: str) -> str:
    flow_dir, flow_file = resolve_flow_path(flow)
    return (flow_dir / flow_file).absolute().resolve().as_posix()


def construct_chat_page_url(
    flow_path: str, flow_dir: Path, pfs_port, url_params: dict, enable_internal_features: bool
) -> str:
    from promptflow._sdk._service.utils.utils import encrypt_flow_path

    # Todo: use base64 encode for now, will consider whether need use encryption or use db to store flow path info
    query_dict = {"flow": encrypt_flow_path(flow_path), **url_params}
    if enable_internal_features:
        query_dict["enable_internal_features"] = "true"
    query_params = urlencode(query_dict)

    return urlunparse(("http", f"127.0.0.1:{pfs_port}", "/v1.0/ui/chat", "", query_params, ""))
