# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import typing
from dataclasses import dataclass

from promptflow._cli._params import base_params
from promptflow._cli._utils import activate_action
from promptflow._sdk._pf_client import PFClient

_client: typing.Optional[PFClient] = None


def _get_pf_client() -> PFClient:
    global _client
    if _client is None:
        _client = PFClient()
    return _client


def add_trace_parser(subparsers: argparse._SubParsersAction):
    trace_parser = subparsers.add_parser(
        "trace",
        description="[Experimental] A CLI tool to manage traces for prompt flow.",
        help="[Experimental] pf trace. This is an experimental feature, and may change at any time.",
    )
    subparsers = trace_parser.add_subparsers()
    add_delete_trace_params(subparsers)
    trace_parser.set_defaults(action="trace")


def dispatch_trace_cmds(args: argparse.Namespace):
    if args.sub_action == "delete":
        delete_trace(args)


def _add_param_run(parser):
    parser.add_argument("--run", type=str, help="Name of the run.")


def _add_param_session(parser):
    parser.add_argument("--session", type=str, help="Id of the session.")


def _add_param_started_before(parser):
    parser.add_argument("--started-before", type=str, help="Date and time in ISO 8601 format.")


def add_delete_trace_params(subparsers):
    epilog = """
Examples:

# Delete traces
pf trace delete --run <run>
pf trace delete --session <session>
pf trace delete --session <session> --started-before <isoformat-string>
"""
    add_params = [
        _add_param_run,
        _add_param_session,
        _add_param_started_before,
    ] + base_params
    activate_action(
        name="delete",
        description=None,
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Delete traces comes from run, session or by time.",
        action_param_name="sub_action",
    )


# use @dataclass for validation and strong type
@dataclass
class DeleteTraceParser:
    run: typing.Optional[str] = None
    session: typing.Optional[str] = None
    started_before: typing.Optional[str] = None


def delete_trace(args: argparse.Namespace) -> None:
    _get_pf_client()._traces.delete(
        run=args.run,
        session=args.session,
        started_before=args.started_before,
    )
