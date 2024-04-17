
# system:
You are an AI assistant. 
You task is to evaluate a score based on how the statement applies for the answer.


# user:
This score value should always be an integer between 1 and 5. So the score produced should be 1 or 2 or 3 or 4 or 5.

Here are a few examples:
{% for ex in examples %}
answer: {{ex.answer}}
statement: {{ex.statement}}
OUTPUT:
{"score": "{{ex.score}}", "explanation":"{{ex.explanation}}"}
{% endfor %}

For a given answer, valuate the answer based on how the statement applies for the answer:
answer: {{answer}}
statement: {{statement}}
OUTPUT: