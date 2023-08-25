import asyncio
import logging
import uuid
import openai
import os
from abc import ABC, abstractmethod
import tiktoken
from dotenv import load_dotenv
from prompt import PromptLimitException


class AOAI(ABC):
    def __init__(self, **kwargs):
        openai.api_key = os.environ.get("OPENAI_API_KEY")
        openai.api_base = os.environ.get("OPENAI_API_BASE")
        openai.api_version = os.environ.get("OPENAI_API_VERSION")
        openai.api_type = os.environ.get("API_TYPE") or "azure"
        self.default_engine = None
        self.engine = kwargs.pop('module', None) or os.environ.get("MODULE")
        self.total_tokens = 4000
        self.max_tokens = kwargs.pop('max_tokens', None) or os.environ.get("MAX_TOKENS") or 1200
        if self.engine == "gpt-4-32k":
            self.total_tokens = 31000
        if self.engine == "gpt-4":
            self.total_tokens = 7000
        if self.engine == "gpt-3.5-turbo-16k":
            self.total_tokens = 15000
        if self.max_tokens > self.total_tokens:
            raise ValueError(f"max_tokens must be less than total_tokens, "
                             f"total_tokens is {self.total_tokens}, max_tokens is {self.max_tokens}")
        self.tokens_limit = self.total_tokens - self.max_tokens

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

    async def aquery(self, text, **kwargs):
        stream = kwargs.pop("stream", False)
        for i in range(3):
            try:
                if not stream:
                    res = await self.aquery_with_nostream(text, **kwargs)
                    return res
                else:
                    res = await self.aquery_with_stream(text, **kwargs)
                    return "".join(res)
            except Exception as e:
                logging.error(f"llm response error, message={e}, "
                              f"will retry request llm after {(i + 1) * (i + 1)} seconds.")
                await asyncio.sleep((i + 1) * (i + 1))
        raise Exception("llm response error, and retry 3 times, but still failed.")

    @abstractmethod
    def query_with_nostream(self, text, **kwargs):
        pass

    @abstractmethod
    def query_with_stream(self, text, **kwargs):
        pass

    @abstractmethod
    async def aquery_with_nostream(self, text, **kwargs):
        pass

    @abstractmethod
    async def aquery_with_stream(self, text, **kwargs):
        pass


class LLM(AOAI):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.default_engine = "text-davinci-003"
        self.engine = self.engine or self.default_engine

    def query_with_nostream(self, text, **kwargs):
        prompt = self.create_prompt(text)
        self.validate_tokens(prompt)
        temperature = kwargs.pop("temperature", 0.1)
        response = openai.Completion.create(
            engine=self.engine,
            prompt=prompt,
            temperature=temperature,
            max_tokens=self.max_tokens,
            stream=False,
            **kwargs,
        )
        return response["choices"][0]["text"]

    def query_with_stream(self, text, **kwargs):
        prompt = self.create_prompt(text)
        self.validate_tokens(prompt)
        temperature = kwargs.pop("temperature", 0.1)
        response = openai.Completion.create(
            engine=self.engine,
            prompt=prompt,
            temperature=temperature,
            max_tokens=self.max_tokens,
            stream=True,
            **kwargs,
        )
        for chunk in response:
            yield chunk["choices"][0]["text"]

    async def aquery_with_nostream(self, text, **kwargs):
        prompt = self.create_prompt(text)
        self.validate_tokens(prompt)
        temperature = kwargs.pop("temperature", 0.1)
        response = await openai.Completion.acreate(
            engine=self.engine,
            prompt=prompt,
            temperature=temperature,
            max_tokens=self.max_tokens,
            stream=False,
            **kwargs,
        )
        return response["choices"][0]["text"]

    async def aquery_with_stream(self, text, **kwargs):
        prompt = self.create_prompt(text)
        self.validate_tokens(prompt)
        temperature = kwargs.pop("temperature", 0.1)
        response = await openai.Completion.acreate(
            engine=self.engine,
            prompt=prompt,
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
            raise PromptLimitException(message)

    def create_prompt(self, text):
        return text


class ChatLLM(AOAI):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.default_engine = "gpt-3.5-turbo"
        self.engine = self.engine or self.default_engine
        self.system_prompt = "You are a Python engineer."
        self.conversation = dict()

    def query_with_nostream(self, text, **kwargs):
        convo_id = kwargs.pop('conversation', None)
        messages = self.create_prompt(text, convo_id)
        self.validate_tokens(messages)
        temperature = kwargs.pop("temperature", 0.1)
        response = openai.ChatCompletion.create(
            engine=self.engine,
            messages=messages,
            temperature=temperature,
            max_tokens=self.max_tokens,
            stream=False,
            **kwargs,
        )
        response_role = response["choices"][0]["message"]["role"]
        full_response = response["choices"][0]["message"]["content"]
        self.add_to_conversation(text, "user", convo_id=convo_id)
        self.add_to_conversation(full_response, response_role, convo_id=convo_id)
        return full_response

    def query_with_stream(self, text, **kwargs):
        convo_id = kwargs.pop('conversation', None)
        messages = self.create_prompt(text, convo_id)
        self.validate_tokens(messages)
        temperature = kwargs.pop("temperature", 0.1)
        response = openai.ChatCompletion.create(
            engine=self.engine,
            messages=messages,
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
        self.add_to_conversation(text, "user", convo_id=convo_id)
        self.add_to_conversation(full_response, response_role, convo_id=convo_id)

    async def aquery_with_nostream(self, text, **kwargs):
        convo_id = kwargs.pop('conversation', None)
        messages = self.create_prompt(text, convo_id)
        self.validate_tokens(messages)
        temperature = kwargs.pop("temperature", 0.1)
        response = await openai.ChatCompletion.acreate(
            engine=self.engine,
            messages=messages,
            temperature=temperature,
            max_tokens=self.max_tokens,
            stream=False,
            **kwargs,
        )
        response_role = response["choices"][0]["message"]["role"]
        full_response = response["choices"][0]["message"]["content"]
        self.add_to_conversation(text, "user", convo_id=convo_id)
        self.add_to_conversation(full_response, response_role, convo_id=convo_id)
        return full_response

    async def aquery_with_stream(self, text, **kwargs):
        convo_id = kwargs.pop('conversation', None)
        messages = self.create_prompt(text, convo_id)
        self.validate_tokens(messages)
        temperature = kwargs.pop("temperature", 0.1)
        response = await openai.ChatCompletion.acreate(
            engine=self.engine,
            messages=messages,
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
        self.add_to_conversation(text, "user", convo_id=convo_id)
        self.add_to_conversation(full_response, response_role, convo_id=convo_id)

    def get_unique_convo_id(self):
        return str(uuid.uuid4()).replace('-', '')

    def add_to_conversation(self, message: str, role: str, convo_id: str) -> None:
        """
        Add a message to the conversation
        """
        if type(convo_id) is str:
            self.conversation[convo_id].append({"role": role, "content": message})

    def del_conversation(self, convo_id: str) -> None:
        if convo_id in self.conversation:
            del self.conversation[convo_id]

    def init_conversation(self, convo_id: str, system_prompt) -> None:
        """
        Init a new conversation
        """
        if type(convo_id) is str:
            self.conversation[convo_id] = [{"role": "system", "content": system_prompt}]

    def get_tokens_count(self, messages: list[dict]) -> int:
        """
        Get token count
        """
        num_tokens = 0
        for message in messages:
            # every message follows <im_start>{role/name}\n{content}<im_end>\n
            num_tokens += 5
            for key, value in message.items():
                if value:
                    num_tokens += self.count_tokens(value)
                if key == "name":  # if there's a name, the role is omitted
                    num_tokens += 5  # role is always required and always 1 token
        num_tokens += 5  # every reply is primed with <im_start>assistant
        return num_tokens

    def validate_tokens(self, messages: list[dict]) -> None:
        total_tokens = self.get_tokens_count(messages)
        if total_tokens > self.tokens_limit:
            message = f"token count {total_tokens} exceeds limit {self.tokens_limit}"
            raise PromptLimitException(message)

    def create_prompt(self, text: str, convo_id: str = None):
        unique_convo_id = self.get_unique_convo_id()
        convo_id = convo_id or unique_convo_id
        if convo_id not in self.conversation:
            self.init_conversation(convo_id=convo_id, system_prompt=self.system_prompt)

        _conversation = self.conversation[convo_id] + [{"role": "user", "content": text}]

        while self.get_tokens_count(_conversation) > self.tokens_limit and len(_conversation) > 2:
            _conversation.pop(1)

        if unique_convo_id == convo_id:
            self.del_conversation(convo_id=unique_convo_id)

        return _conversation


if __name__ == "__main__":
    load_dotenv()
    llm = LLM()
    print(llm.query(text='how are you?'))
    res = llm.query_with_stream(text='how are you?')
    for item in res:
        print(item)
