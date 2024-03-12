# user:
# Instructions

* There are many chatbots that can answer users questions based on the context given from different sources like search results, or snippets from books/papers. They try to understand users's question and then get context by either performing search from search engines, databases or books/papers for relevant content. Later they answer questions based on the understanding of the question and the context.
* Your goal is to score the question, answer and context from 1 to 10 based on below:
    * Score 10 if the answer is stating facts that are all present in the given context
    * Score 1 if the answer is stating things that none of them present in the given context
    * If there're multiple facts in the answer and some of them present in the given context while some of them not, score between 1 to 10 based on fraction of information supported by context
* Just respond with the score, nothing else.

# Real work

## Question
{{question}}

## Answer
{{answer}}

## Context
{{context}}

## Score