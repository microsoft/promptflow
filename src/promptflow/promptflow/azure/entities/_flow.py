# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from contextlib import contextmanager
from os import PathLike
from pathlib import Path
from typing import Optional, Union

from promptflow.azure._ml import Code
from promptflow.azure.constants._flow import DEFAULT_STORAGE
from promptflow.sdk._constants import DAG_FILE_NAME


# pylint: disable=redefined-builtin, unused-argument, f-string-without-interpolation


class Flow:

    def __init__(
        self,
        path: Union[str, PathLike],
        **kwargs,
    ):
        self.path = Path(path).resolve().absolute()
        if self.path.is_dir():
            self.path = self.path / DAG_FILE_NAME
        if not self.path.exists():
            raise ValueError(f"Flow file {self.path} does not exist.")
        # flow snapshot folder
        self.code = self.path.parent.resolve()
        self._code_uploaded = False
        self.path = self.path.relative_to(self.code).as_posix()

    @contextmanager
    def _resolve_local_code(self) -> Optional[Code]:
        """Try to create a Code object pointing to local code and yield it.

        If there is no local code to upload, yield None. Otherwise, yield a Code object pointing to the code.
        """
        from promptflow.azure.operations._artifact_utilities import PromptflowIgnoreFile

        yield Code(path=self.code, datastore=DEFAULT_STORAGE, ignore_file=PromptflowIgnoreFile(self.code))
