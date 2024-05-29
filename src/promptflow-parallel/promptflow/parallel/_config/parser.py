# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import itertools
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from promptflow.parallel._config.model import ParallelRunConfig, output_file_pattern


def parse(args: List[str]) -> ParallelRunConfig:
    parsed = _do_parse(args)
    return _to_parallel_run_config(parsed)


def _to_parallel_run_config(parsed_args: Namespace) -> ParallelRunConfig:
    return ParallelRunConfig(
        pf_model_dir=parsed_args.pf_model,
        input_dir=next(map(Path, iter(parsed_args.input_assets.values())), None),
        output_dir=parsed_args.output_uri_file or parsed_args.output,
        output_file_pattern=output_file_pattern(parsed_args.append_row_file_name),
        input_mapping=parsed_args.input_mapping,
        side_input_dir=parsed_args.pf_run_outputs,
        connections_override=_get_connection_overrides(parsed_args),
        debug_output_dir=parsed_args.pf_debug_info,
        logging_level=parsed_args.logging_level,
    )


def _get_connection_overrides(parsed_args: Namespace) -> Dict[str, str]:
    return dict(
        itertools.chain(
            _retrieve_connection_overrides(parsed_args.pf_connections),
            _retrieve_connection_overrides(parsed_args.pf_deployment_names),
            _retrieve_connection_overrides(parsed_args.pf_model_names),
        )
    )


def _retrieve_connection_overrides(arg: str) -> Iterable[Tuple[str, str]]:
    connection = arg.strip().strip('"') if arg else None
    if not connection:
        return
    connection_params = connection.split(",")
    for connection_param in connection_params:
        if connection_param.strip() == "":
            continue
        key, value = connection_param.split("=")[0:2]
        yield key.strip(), value.strip()


def _do_parse(args: List[str]) -> Namespace:
    parser = ArgumentParser(description="Prompt Flow Parallel Run Config")
    parser.add_argument("--amlbi_pf_model", dest="pf_model", type=Path, required=False, default=None)
    parser.add_argument("--amlbi_pf_connections", dest="pf_connections", required=False)
    parser.add_argument("--amlbi_pf_deployment_names", dest="pf_deployment_names", required=False)
    parser.add_argument("--amlbi_pf_model_names", dest="pf_model_names", required=False)
    parser.add_argument("--output_uri_file", dest="output_uri_file", type=Path, required=False, default=None)
    parser.add_argument("--output", dest="output", type=Path, required=False, default=None)
    parser.add_argument(
        "--append_row_file_name", dest="append_row_file_name", required=False, default="parallel_run_step.jsonl"
    )
    parser.add_argument("--amlbi_pf_run_outputs", dest="pf_run_outputs", type=Path, required=False, default=None)
    parser.add_argument("--amlbi_pf_debug_info", dest="pf_debug_info", type=Path, required=False, default=None)
    parser.add_argument("--logging_level", dest="logging_level", required=False, default="INFO")
    parsed_args, unknown_args = parser.parse_known_args(args)

    setattr(parsed_args, "input_mapping", _parse_prefixed_args(unknown_args, "--pf_input_"))
    setattr(parsed_args, "input_assets", _parse_prefixed_args(unknown_args, "--input_asset_"))

    return parsed_args


def _parse_prefixed_args(args: List[str], prefix: str) -> Dict[str, str]:
    """parse prompt flow input args to dictionary.

    Example:
        >>> argv = ["--pf_input_uri=uri1", "--pf_input_arg2", "arg2"]
        >>> _parse_prefixed_args(argv, "--pf_input_uri")
        {"uri": "uri1"}
    """
    parsed = {}
    pre_arg_name = None
    for _, arg in enumerate(args):
        if arg.startswith(prefix):
            if "=" in arg:
                arg_name, arg_value = arg.split("=")
                if len(arg_name) > len(prefix):
                    parsed[arg_name[len(prefix) :]] = arg_value
            elif pre_arg_name is None:
                pre_arg_name = arg[len(prefix) :]
                continue
        elif pre_arg_name is not None:
            parsed[pre_arg_name] = arg
        pre_arg_name = None
    return parsed
