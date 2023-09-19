import asyncio
import logging
import time
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
        openai.api_type = os.environ.get("API_TYPE")
        openai.organization = os.environ.get("ORGANIZATION")
        self.default_engine = None
        self.engine = kwargs.pop('model', None) or os.environ.get("MODEL")
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
        for i in range(3):
            try:
                if not stream:
                    return self.query_with_no_stream(text, **kwargs)
                else:
                    return "".join(self.query_with_stream(text, **kwargs))
            except Exception as e:
                logging.error(f"Query failed, message={e}, "
                              f"will retry request llm after {(i + 1) * (i + 1)} seconds.")
                time.sleep((i + 1) * (i + 1))
        raise Exception("Query failed, and retry 3 times, but still failed.")

    async def async_query(self, text, **kwargs):
        stream = kwargs.pop("stream", False)
        for i in range(3):
            try:
                if not stream:
                    res = await self.async_query_with_no_stream(text, **kwargs)
                    return res
                else:
                    res = await self.async_query_with_stream(text, **kwargs)
                    return "".join(res)
            except Exception as e:
                logging.error(f"llm response error, message={e}, "
                              f"will retry request llm after {(i + 1) * (i + 1)} seconds.")
                await asyncio.sleep((i + 1) * (i + 1))
        raise Exception("llm response error, and retry 3 times, but still failed.")

    @abstractmethod
    def query_with_no_stream(self, text, **kwargs):
        pass

    @abstractmethod
    def query_with_stream(self, text, **kwargs):
        pass

    @abstractmethod
    async def async_query_with_no_stream(self, text, **kwargs):
        pass

    @abstractmethod
    async def async_query_with_stream(self, text, **kwargs):
        pass


class ChatLLM(AOAI):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.default_engine = "gpt-3.5-turbo"
        self.engine = self.engine or self.default_engine
        self.system_prompt = "You are a Python engineer."
        self.conversation = dict()

    def query_with_no_stream(self, text, **kwargs):
        conversation_id = kwargs.pop('conversation', None)
        messages = self.create_prompt(text, conversation_id)
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
        self.add_to_conversation(text, "user", conversation_id=conversation_id)
        self.add_to_conversation(full_response, response_role, conversation_id=conversation_id)
        return full_response

    def query_with_stream(self, text, **kwargs):
        conversation_id = kwargs.pop('conversation', None)
        messages = self.create_prompt(text, conversation_id)
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
        self.add_to_conversation(text, "user", conversation_id=conversation_id)
        self.add_to_conversation(full_response, response_role, conversation_id=conversation_id)

    async def async_query_with_no_stream(self, text, **kwargs):
        conversation_id = kwargs.pop('conversation', None)
        messages = self.create_prompt(text, conversation_id)
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
        self.add_to_conversation(text, "user", conversation_id=conversation_id)
        self.add_to_conversation(full_response, response_role, conversation_id=conversation_id)
        return full_response

    async def async_query_with_stream(self, text, **kwargs):
        conversation_id = kwargs.pop('conversation', None)
        messages = self.create_prompt(text, conversation_id)
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
        self.add_to_conversation(text, "user", conversation_id=conversation_id)
        self.add_to_conversation(full_response, response_role, conversation_id=conversation_id)

    def get_unique_conversation_id(self):
        return str(uuid.uuid4()).replace('-', '')

    def add_to_conversation(self, message: str, role: str, conversation_id: str) -> None:
        """
        Add a message to the conversation
        """
        if type(conversation_id) is str:
            self.conversation[conversation_id].append({"role": role, "content": message})

    def del_conversation(self, conversation_id: str) -> None:
        if conversation_id in self.conversation:
            del self.conversation[conversation_id]

    def init_conversation(self, conversation_id: str, system_prompt) -> None:
        """
        Init a new conversation
        """
        if type(conversation_id) is str:
            self.conversation[conversation_id] = [{"role": "system", "content": system_prompt}]

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

    def create_prompt(self, text: str, conversation_id: str = None):
        unique_conversation_id = self.get_unique_conversation_id()
        conversation_id = conversation_id or unique_conversation_id
        if conversation_id not in self.conversation:
            self.init_conversation(conversation_id=conversation_id, system_prompt=self.system_prompt)

        _conversation = self.conversation[conversation_id] + [{"role": "user", "content": text}]

        while self.get_tokens_count(_conversation) > self.tokens_limit and len(_conversation) > 2:
            _conversation.pop(1)

        if unique_conversation_id == conversation_id:
            self.del_conversation(conversation_id=unique_conversation_id)

        return _conversation


if __name__ == "__main__":
    load_dotenv()
    llm = ChatLLM()
    print(llm.query(text='how are you?'))
    res = llm.query_with_stream(text='how are you?')
    for item in res:
        print(item)
