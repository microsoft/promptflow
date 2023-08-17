import uuid
import openai
import os
from abc import ABC, abstractmethod
import tiktoken
from dotenv import load_dotenv
from prompt import PromptException


class AOAI(ABC):
    def __init__(self, **kwargs):
        openai.api_key = os.environ.get("OPENAI_API_KEY")
        openai.api_base = os.environ.get("OPENAI_API_BASE")
        openai.api_version = os.environ.get("OPENAI_API_VERSION")
        openai.api_type = "azure"
        self.default_engine = None
        self.engine = kwargs.pop('module', None) or os.environ.get("MODULE")
        self.max_tokens = kwargs.pop('max_tokens', None) or os.environ.get("MAX_TOKENS") or 4000
        if self.engine == "gpt-4-32k":
            self.max_tokens = 31000
        if self.engine == "gpt-4":
            self.max_tokens = 7000
        if self.engine == "gpt-3.5-turbo-16k":
            self.max_tokens = 15000
        self.tokens_limit = kwargs.pop('tokens_limit', None) or max(self.max_tokens - 1000, self.max_tokens // 2)

    def count_tokens(self, text: str) -> int:
        try:
            encoding = tiktoken.encoding_for_model(self.engine)
        except KeyError:
            encoding = tiktoken.encoding_for_model(self.default_engine)
        return len(encoding.encode(text))

    def query(self, text, **kwargs):
        stream = kwargs.pop("stream", False)
        if not stream:
            return self.query_with_nostream(text, **kwargs)
        else:
            return "".join(self.query_with_stream(text, **kwargs))

    @abstractmethod
    def query_with_nostream(self, text, **kwargs):
        pass

    @abstractmethod
    def query_with_stream(self, text, **kwargs):
        pass


class LLM(AOAI):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.default_engine = "text-davinci-003"
        self.engine = self.engine or self.default_engine

    def query_with_nostream(self, text, **kwargs):
        self.validate_tokens(text)
        temperature = kwargs.pop("temperature", 0.1)
        response = openai.Completion.create(
            engine=self.engine,
            prompt=text,
            temperature=temperature,
            max_tokens=self.max_tokens,
            stream=False,
            **kwargs,
        )
        return response["choices"][0]["text"]

    def query_with_stream(self, text, **kwargs):
        self.validate_tokens(text)
        temperature = kwargs.pop("temperature", 0.1)
        response = openai.Completion.create(
            engine=self.engine,
            prompt=text,
            temperature=temperature,
            max_tokens=self.max_tokens,
            stream=True,
            **kwargs,
        )
        for chunk in response:
            yield chunk["choices"][0]["text"]

    def validate_tokens(self, text: str) -> None:
        total_tokens = self.count_tokens(text)
        if total_tokens > self.tokens_limit:
            message = f"token count {total_tokens} exceeds limit {self.tokens_limit}"
            raise PromptException(message)


class ChatLLM(AOAI):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.default_engine = "gpt-3.5-turbo"
        self.engine = self.engine or self.default_engine
        self.system_prompt = "You are a Python engineer."
        self.conversation = dict()
        self.unique_convo_id = None

    def query_with_nostream(self, text, **kwargs):
        try:
            convo_id = kwargs.pop('conversation', self.get_unique_convo_id())
            if convo_id not in self.conversation:
                self.reset(convo_id=convo_id, system_prompt=self.system_prompt)
            self.add_to_conversation(text, "user", convo_id=convo_id)
            self.validate_tokens(convo_id=convo_id)
            temperature = kwargs.pop("temperature", 0.1)
            response = openai.ChatCompletion.create(
                engine=self.engine,
                messages=self.conversation[convo_id],
                temperature=temperature,
                max_tokens=self.max_tokens,
                stream=False,
                **kwargs,
            )
            response_role = response["choices"][0]["message"]["role"]
            full_response = response["choices"][0]["message"]["content"]
            self.add_to_conversation(full_response, response_role, convo_id=convo_id)
            return full_response
        except Exception as e:
            raise e
        finally:
            self.del_conversation(convo_id=self.unique_convo_id)

    def query_with_stream(self, text, **kwargs):
        try:
            convo_id = kwargs.pop('conversation', self.get_unique_convo_id())
            if convo_id not in self.conversation:
                self.reset(convo_id=convo_id, system_prompt=self.system_prompt)
            self.add_to_conversation(text, "user", convo_id=convo_id)
            self.validate_tokens(convo_id=convo_id)
            temperature = kwargs.pop("temperature", 0.1)
            response = openai.ChatCompletion.create(
                engine=self.engine,
                messages=self.conversation[convo_id],
                temperature=temperature,
                max_tokens=self.max_tokens,
                stream=True,
                **kwargs,
            )

            response_role = None
            full_response = ""
            for chunk in response:
                delta = chunk["choices"][0]["delta"]
                if "role" in delta:
                    response_role = delta["role"]
                if "content" in delta:
                    content = delta["content"]
                    full_response += content
                    yield content
            self.add_to_conversation(full_response, response_role, convo_id=convo_id)
        except Exception as e:
            raise e
        finally:
            self.del_conversation(convo_id=self.unique_convo_id)

    def get_unique_convo_id(self):
        self.unique_convo_id = str(uuid.uuid4()).replace('-', '')
        return self.unique_convo_id

    def add_to_conversation(self, message: str, role: str, convo_id: str) -> None:
        """
        Add a message to the conversation
        """
        self.conversation[convo_id].append({"role": role, "content": message})

    def del_conversation(self, convo_id: str) -> None:
        if convo_id in self.conversation:
            del self.conversation[convo_id]

    def validate_tokens(self, convo_id: str) -> None:
        while self.get_tokens_count(convo_id) > self.tokens_limit and len(self.conversation[convo_id]) > 2:
            self.conversation[convo_id].pop(1)
        total_tokens = self.get_tokens_count(convo_id)
        if total_tokens > self.tokens_limit:
            message = f"token count {total_tokens} exceeds limit {self.tokens_limit}"
            raise PromptException(message)

    def reset(self, convo_id: str, system_prompt) -> None:
        """
        Reset the conversation
        """
        self.conversation[convo_id] = [{"role": "system", "content": system_prompt}]

    def get_tokens_count(self, convo_id: str) -> int:
        """
        Get token count
        """
        num_tokens = 0
        for message in self.conversation[convo_id]:
            # every message follows <im_start>{role/name}\n{content}<im_end>\n
            num_tokens += 5
            for key, value in message.items():
                if value:
                    num_tokens += self.count_tokens(value)
                if key == "name":  # if there's a name, the role is omitted
                    num_tokens += 5  # role is always required and always 1 token
        num_tokens += 5  # every reply is primed with <im_start>assistant
        return num_tokens


if __name__ == "__main__":
    load_dotenv()
    llm = LLM()
    print(llm.query(text='how are you?'))
    res = llm.query_with_stream(text='how are you?')
    for item in res:
        print(item)