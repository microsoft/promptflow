import pytest
from promptflow.contracts.types import Secret, PromptTemplate


@pytest.mark.unittest
def test_secret():
    secret = Secret('my_secret')
    secret.set_secret_name('secret_name')
    assert secret.secret_name == 'secret_name'


@pytest.mark.unittest
def test_prompt_template():
    prompt = PromptTemplate('my_prompt')
    assert isinstance(prompt, str)
    assert str(prompt) == 'my_prompt'
