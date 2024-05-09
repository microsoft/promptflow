# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import inspect
from pathlib import Path
from typing import Callable, List, Tuple, Union

from promptflow._constants import FLOW_FLEX_YAML, LANGUAGE_KEY
from promptflow._utils.flow_utils import is_flex_flow
from promptflow.exceptions import UserErrorException


def format_signature_type(flow_meta):
    # signature is language irrelevant, so we apply json type system
    # TODO: enable this mapping after service supports more types
    value_type_map = {
        # ValueType.INT.value: SignatureValueType.INT.value,
        # ValueType.DOUBLE.value: SignatureValueType.NUMBER.value,
        # ValueType.LIST.value: SignatureValueType.ARRAY.value,
        # ValueType.BOOL.value: SignatureValueType.BOOL.value,
    }
    for port_type in ["inputs", "outputs", "init"]:
        if port_type not in flow_meta:
            continue
        for port_name, port in flow_meta[port_type].items():
            if port["type"] in value_type_map:
                port["type"] = value_type_map[port["type"]]


def _validate_flow_meta(flow_meta: dict, language: str, code: Path):
    flow_meta["language"] = language
    # TODO: change this implementation to avoid using FlexFlow?
    # this path is actually not used
    from promptflow._sdk.entities._flows import FlexFlow

    flow = FlexFlow(path=code / FLOW_FLEX_YAML, code=code, data=flow_meta, entry=flow_meta["entry"])
    flow._validate(raise_error=True)


def infer_signature_for_flex_flow(
    entry: Union[Callable, str],
    *,
    language: str,
    code: str = None,
    keep_entry: bool = False,
    validate: bool = True,
    include_primitive_output: bool = False,
) -> Tuple[dict, Path, List[str]]:
    """Infer signature of a flow entry."""
    snapshot_list = None
    # resolve entry and code
    if isinstance(entry, str):
        if not code:
            raise UserErrorException("Code path is required when entry is a string.")
        code = Path(code)
        if not code.exists():
            raise UserErrorException(f"Specified code {code} does not exist.")
        if code.is_file():
            snapshot_list = [code.name]
            entry = f"{code.stem}:{entry}"
            code = code.parent

        # import this locally to avoid circular import
        from promptflow._proxy import ProxyFactory

        inspector_proxy = ProxyFactory().create_inspector_proxy(language=language)

        if not inspector_proxy.is_flex_flow_entry(entry):
            raise UserErrorException(f"Entry {entry} is not a valid entry for flow.")

        # TODO: extract description?
        flow_meta = inspector_proxy.get_entry_meta(entry=entry, working_dir=code)
    elif code is not None:
        # TODO: support specifying code when inferring signature?
        raise UserErrorException(
            "Code path will be the parent of entry source " "and can't be customized when entry is a callable."
        )
    elif inspect.isclass(entry) or inspect.isfunction(entry):
        if inspect.isclass(entry):
            if not hasattr(entry, "__call__"):
                raise UserErrorException("Class entry must have a __call__ method.")
            f, cls = entry.__call__, entry
        else:
            f, cls = entry, None

        # callable entry must be of python, so we directly import from promptflow._core locally here
        from promptflow._core.tool_meta_generator import generate_flow_meta_dict_by_object

        flow_meta = generate_flow_meta_dict_by_object(f, cls)
        source_path = Path(inspect.getfile(entry))
        code = source_path.parent
        # TODO: should we handle the case that entry is not defined in root level of the source?
        flow_meta["entry"] = f"{source_path.stem}:{entry.__name__}"
    else:
        raise UserErrorException("Entry must be a function or a class.")

    format_signature_type(flow_meta)

    if validate:
        _validate_flow_meta(flow_meta, language, code)

    if include_primitive_output and "outputs" not in flow_meta:
        flow_meta["outputs"] = {
            "output": {
                "type": "string",
            }
        }

    keys_to_keep = ["inputs", "outputs", "init"]
    if keep_entry:
        keys_to_keep.append("entry")
    filtered_meta = {k: flow_meta[k] for k in keys_to_keep if k in flow_meta}
    return filtered_meta, code, snapshot_list


def merge_flow_signature(extracted, signature_overrides):
    if not signature_overrides:
        signature_overrides = {}

    signature = {}
    for key in ["inputs", "outputs", "init"]:
        if key in extracted:
            signature[key] = extracted[key]
        elif key in signature_overrides:
            raise UserErrorException(f"Provided signature for {key}, which can't be overridden according to the entry.")

        if key not in signature_overrides:
            continue

        if set(extracted[key].keys()) != set(signature_overrides[key].keys()):
            raise UserErrorException(
                f"Provided signature of {key} does not match the entry.\n"
                f"Ports from signature: {', '.join(signature_overrides[key].keys())}\n"
                f"Ports from entry: {', '.join(signature[key].keys())}\n"
            )

        # TODO: merge the signature
        signature[key] = signature_overrides[key]

    return signature


def update_signatures(code: Path, data: dict) -> bool:
    """Update signatures for flex flow. Raise validation error if signature is not valid."""
    if not is_flex_flow(yaml_dict=data):
        return False
    entry = data.get("entry")
    signatures, _, _ = infer_signature_for_flex_flow(
        entry=entry,
        code=code.as_posix(),
        language=data.get(LANGUAGE_KEY, "python"),
        validate=False,
        include_primitive_output=True,
    )
    # TODO: allow user only specify partial signatures in the yaml
    merged_signatures = merge_flow_signature(
        extracted=signatures,
        signature_overrides=data,
    )
    updated = False
    for field in ["inputs", "outputs", "init"]:
        if merged_signatures.get(field) != data.get(field):
            updated = True
    data.update(merged_signatures)
    from promptflow._sdk.entities._flows import FlexFlow

    FlexFlow(path=code / FLOW_FLEX_YAML, code=code, data=data, entry=entry)._validate(raise_error=True)
    return updated
