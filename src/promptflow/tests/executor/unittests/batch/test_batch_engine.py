from pathlib import Path
from unittest.mock import patch

import pytest

from promptflow._core._errors import UnexpectedError
from promptflow.batch import BatchEngine
from promptflow.exceptions import ErrorTarget

from ...utils import get_yaml_file


@pytest.mark.unittest
class TestBatchEngine:
    def test_batch_engine_error(self):
        with pytest.raises(UnexpectedError) as e:
            with patch(
                "promptflow.batch._batch_inputs_processor.BatchInputsProcessor.process_batch_inputs"
            ) as mock_func:
                mock_func.side_effect = Exception("test error")
                batch_engine = BatchEngine(get_yaml_file("csharp_flow"))
                batch_engine.run({}, {}, Path("."))
        assert e.value.target == ErrorTarget.BATCH
        assert isinstance(e.value.inner_exception, Exception)
        assert e.value.error_codes == ["SystemError", "UnexpectedError"]
        assert (
            e.value.message == "Unexpected error occurred while executing the batch run. Error: (Exception) test error."
        )
