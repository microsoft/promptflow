# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
import os.path
from contextlib import contextmanager
from os import PathLike
from pathlib import Path
from typing import List, Optional, Union

from promptflow._sdk._constants import DAG_FILE_NAME
from promptflow.azure._ml import AdditionalIncludesMixin, Code

from ..._sdk._utils import PromptflowIgnoreFile
from .._constants._flow import DEFAULT_STORAGE

# pylint: disable=redefined-builtin, unused-argument, f-string-without-interpolation


logger = logging.getLogger(__name__)


class Flow(AdditionalIncludesMixin):
    def __init__(
        self,
        path: Union[str, PathLike],
        **kwargs,
    ):
        absolute_path = Path(path).resolve().absolute()
        if absolute_path.is_dir():
            absolute_path = absolute_path / DAG_FILE_NAME
        if not absolute_path.exists():
            raise ValueError(f"Flow file {absolute_path.as_posix()} does not exist.")
        # flow snapshot folder
        self.code = absolute_path.parent.as_posix()
        self._code_uploaded = False
        self.path = absolute_path.name

    # region AdditionalIncludesMixin
    @contextmanager
    def _try_build_local_code(self) -> Optional[Code]:
        """Try to create a Code object pointing to local code and yield it.

        If there is no local code to upload, yield None. Otherwise, yield a Code object pointing to the code.
        """
        with super()._try_build_local_code() as code:
            if isinstance(code, Code):
                # promptflow snapshot has specific ignore logic, like it should ignore `.run` by default
                code._ignore_file = PromptflowIgnoreFile(code.path)
                # promptflow snapshot will always be uploaded to default storage
                code.datastore = DEFAULT_STORAGE
            yield code

    def _get_base_path_for_code(self) -> Path:
        """Get base path for additional includes."""
        # note that self.code is an absolute path, so it is safe to use it as base path
        return Path(self.code)

    def _get_all_additional_includes_configs(self) -> List:
        """Get all additional include configs.
        For flow, its additional include need to be read from dag with a helper function.
        """
        from promptflow._sdk._utils import _get_additional_includes

        return _get_additional_includes(os.path.join(self.code, self.path))

    # endregion
