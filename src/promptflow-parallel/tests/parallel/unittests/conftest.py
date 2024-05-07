# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any, Iterable, Mapping, Optional

import pytest


@pytest.fixture
def save_jsonl():
    @contextmanager
    def save(rows: Optional[Iterable[Mapping[str, Any]]]) -> Path:
        with TemporaryDirectory() as temp_dir:
            with NamedTemporaryFile(mode="w", delete=False, dir=temp_dir, suffix=".jsonl") as f:
                for row in rows or []:
                    f.write(json.dumps(row))
                    f.write("\n")

            yield Path(temp_dir)

    return save
