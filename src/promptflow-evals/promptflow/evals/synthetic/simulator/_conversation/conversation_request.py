# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Dict, Optional

from .conversation_writer import ConversationWriter


class ConversationRequest:
    def __init__(self, template: str, instantiation: Dict[str, str], writer: Optional[ConversationWriter] = None):
        self._template = template
        self._instantiation = instantiation
        self._writer = writer

    @property
    def template(self) -> str:
        return self._template

    @property
    def instantiation_parameters(self) -> Dict[str, str]:
        return self._instantiation

    @property
    def writer(self) -> Optional[ConversationWriter]:
        return self._writer
