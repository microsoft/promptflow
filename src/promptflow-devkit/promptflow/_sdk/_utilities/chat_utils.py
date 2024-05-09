from urllib.parse import urlencode, urlunparse

from promptflow._sdk._service.utils.utils import encrypt_flow_path
from promptflow._utils.flow_utils import resolve_flow_path


def construct_flow_absolute_path(flow: str) -> str:
    flow_dir, flow_file = resolve_flow_path(flow)
    return (flow_dir / flow_file).absolute().resolve().as_posix()


# Todo: use base64 encode for now, will consider whether need use encryption or use db to store flow path info
def construct_chat_page_url(flow, port, url_params, enable_internal_features=False):
    flow_path_dir, flow_path_file = resolve_flow_path(flow)
    flow_path = str(flow_path_dir / flow_path_file)
    encrypted_flow_path = encrypt_flow_path(flow_path)
    query_dict = {"flow": encrypted_flow_path}
    if enable_internal_features:
        query_dict.update({"enable_internal_features": "true", **url_params})
    query_params = urlencode(query_dict)
    return urlunparse(("http", f"127.0.0.1:{port}", "/v1.0/ui/chat", "", query_params, ""))
