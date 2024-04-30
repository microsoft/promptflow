from dataclasses import dataclass
from pathlib import Path

from promptflow.tracing import trace
from promptflow.connections import CustomConnection


from langchain.evaluation import load_evaluator
from langchain.chat_models import AzureChatOpenAI, ChatAnthropic



@dataclass
class Result:
    reasoning: str
    value: str
    score: float


class LangChainEvaluator:
    def __init__(self, custom_connection: CustomConnection):
        self.custom_connection = custom_connection

        # create llm according to the secrets in custom connection
        if "anthropic_api_key" in self.custom_connection.secrets:
            self.llm = ChatAnthropic(temperature=0, anthropic_api_key=self.custom_connection.secrets["anthropic_api_key"])
        elif "openai_api_key" in self.custom_connection.secrets:
            self.llm = AzureChatOpenAI(
                deployment_name="gpt-35-turbo",
                openai_api_key=self.custom_connection.secrets["openai_api_key"],
                azure_endpoint=self.custom_connection.secrets["azure_endpoint"],
                openai_api_type="azure",
                openai_api_version="2023-07-01-preview",
                temperature=0,
            )
        else:
            raise ValueError("No valid API key found in the connection.")
        
        self.evaluator = load_evaluator("criteria", llm=self.llm, criteria="conciseness")

    @trace
    def __call__(
        self, input: str, prediction: str, 
    ) -> Result:
        """Evaluate with langchain evaluator."""

        eval_result = self.evaluator.evaluate_strings(
            prediction=prediction, input=input
        )
        return Result(**eval_result)

