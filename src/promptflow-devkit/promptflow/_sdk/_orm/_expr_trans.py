# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import typing


class ExpressionTranslator:
    """Translate search expression to ORM query."""

    def __init__(self, searchable_fields: typing.List[str]):
        self._searchable_fields = copy.deepcopy(searchable_fields)
