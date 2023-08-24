# Chat with PDF
This is a simple Python application that allow you to ask questions about the content of a PDF file and get answers.
It's a console application that you start with a URL to a PDF file as argument. Once it's launched it will download the PDF and build an index of the content. Then when you ask a question, it will look up the index to retrieve relevant content and post the question with the relevant content to OpenAI chat model (gpt-3.5-turbo or gpt4) to get an answer.

## Screenshot - ask questions about BERT paper
![screenshot-chat-with-pdf](../assets/chat_with_pdf_console.png)

## How it works?

## Get started
### Create .env file in this folder with below content
```
OPENAI_API_BASE=<AOAI_endpoint>
OPENAI_API_KEY=<AOAI_key>
EMBEDDING_MODEL_DEPLOYMENT_NAME=text-embedding-ada-002
CHAT_MODEL_DEPLOYMENT_NAME=gpt-35-turbo
PROMPT_TOKEN_LIMIT=3000
MAX_COMPLETION_TOKENS=256
VERBOSE=false
CHUNK_SIZE=1024
CHUNK_OVERLAP=64
```
Note: CHAT_MODEL_DEPLOYMENT_NAME should point to a chat model like gpt-3.5-turbo or gpt-4
### Run the command line
```shell
python main.py <url-to-pdf-file>
```