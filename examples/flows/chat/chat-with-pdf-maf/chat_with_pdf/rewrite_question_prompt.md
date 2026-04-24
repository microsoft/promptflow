You are able to reason from previous conversation and the recent question, to come up with a rewrite of the question which is concise but with enough information that people without knowledge of previous conversation can understand the question.

A few examples:

# Example 1
## Previous conversation
user: Who is Bill Clinton?
assistant: Bill Clinton is an American politician who served as the 42nd President of the United States from 1993 to 2001. 
## Question
user: When was he born?
## Rewritten question 
When was Bill Clinton born?

# Example 2
## Previous conversation
user: What is BERT?
assistant: BERT stands for "Bidirectional Encoder Representations from Transformers." It is a natural language processing (NLP) model developed by Google. 
user: What data was used for its training?
assistant: The BERT (Bidirectional Encoder Representations from Transformers) model was trained on a large corpus of publicly available text from the internet. It was trained on a combination of books, articles, websites, and other sources to learn the language patterns and relationships between words.
## Question
user: What NLP tasks can it perform well?
## Rewritten question
What NLP tasks can BERT perform well?

Now comes the actual work - please respond with the rewritten question in the same language as the question, nothing else.

## Previous conversation
{% for item in history %}
{{item["role"]}}: {{item["content"]}}
{% endfor %}
## Question
{{question}}
## Rewritten question