# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse


def add_trace_parser(subparsers: argparse._SubParsersAction):
    trace_parser = subparsers.add_parser("trace", description="A CLI tool to manage traces", help="pf trace")
    trace_parser.set_defaults(action="trace")


def dispatch_trace_cmds(args: argparse.Namespace):
    if args.sub_action == "delete":
        delete_trace(args)


def delete_trace(args: argparse.Namespace):
    pass
