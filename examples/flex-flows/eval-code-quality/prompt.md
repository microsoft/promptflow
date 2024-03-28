
# system:
You are an AI assistant. 
You task is to evaluate the code based on correctness, readability.


# user:
This correctness value should always be an integer between 1 and 5. So the correctness produced should be 1 or 2 or 3 or 4 or 5.
This readability value should always be an integer between 1 and 5. So the correctness produced should be 1 or 2 or 3 or 4 or 5.

Here are a few examples:
{% for ex in examples %}
Code: {{ex.code}}
OUTPUT:
{"correctness": "{{ex.correctness}}", "readability": "{{ex.readability}}", "explanation":"{{ex.explanation}}"}
{% endfor %}

For a given code, valuate the code based on correctness, readability:
Code: {{code}}
OUTPUT: