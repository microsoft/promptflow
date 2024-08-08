# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


from .toy_flex_dep import DepFunc


class ToyEvaluator:
    """
    Simple flex flow-based evaluator to test the save/load bug in flex flows, wherin
    Flex flows that were saved and loaded would fail to run if they had relative imports.
    Although built-in evaluators have had their relative imports wrapped, we still want
    to test this bug to ensure that custom evaluators written by customers don't have to
    deal with this problem.
    """

    def __init__(self):
        pass

    def __call__(self):
        return DepFunc()
