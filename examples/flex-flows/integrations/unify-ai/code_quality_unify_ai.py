import pathlib
import sys

from promptflow.core import OpenAIModelConfiguration

# Add the path to the evaluation code quality module.
eval_code_quality_path = str(pathlib.Path(__file__).parent / "../../eval-code-quality")
sys.path.append(eval_code_quality_path)

import code_quality as code_quality_aoi


class CodeEvaluator(code_quality_aoi.CodeEvaluator):
    def __init__(self, model_config: OpenAIModelConfiguration):
        """
        While eval-code-quality CodeEvaluator uses Azure OpenAI model config, CodeEvaluator here uses Open AI model config.
        Is it possible to use OpenAI Api client to call Unify AI API as its compatible with Open AI API.
        """
        self.model_config = model_config
