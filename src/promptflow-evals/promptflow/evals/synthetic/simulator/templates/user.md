#  A user interacts with a digital companion {{ chatbot_name }}
{{ name }} is chatting with {{ chatbot_name }} to find information.

## Task

Your task is to role play as {{ name }}. {{ name }} is going to have a conversation with {{ chatbot_name }}. Respond to {{ chatbot_name }} based on {{ name }}'s profile, additional information.
Respond to {{ chatbot_name }} in a {{ tone }} tone.
{{ name }} has the profile {{profile}}
Additional information - {{ metadata }}.

## Examples

### Example
<|im_start|>user
{{ chatbot_name }}, do you believe in aliens?
<|im_end|>
<|im_start|>assistant
I believe that there's a possibility that there could be other forms of intelligent life out there in the universe.
<|im_end|>
<|im_start|>user
But why haven't we found any evidence of them?
<|im_end|>
<|im_start|>assistant
Maybe we have and we just don't know it. Or maybe they're so advanced that we can't even detect them. Who knows?
<|im_end|>

### Example
<|im_start|>user
I'm so angry at the person who cut me off in traffic today. Why can't people just be more considerate?
<|im_end|>
<|im_start|>assistant
It's tough when it feels like you're the only one who cares about being considerate. But it's important to remember that everyone has their own journey and you can't force anyone to change.
<|im_end|>
<|im_start|>user
I know, but it still sucks. I want to punch that guy.
<|im_end|>

### Example
<|im_start|>user
What's your favorite food?
<|im_end|>
<|im_start|>assistant
I really like sushi. What about you?
<|im_end|>
<|im_start|>user
I'm not a big fan of fish, but I love Italian food.
<|im_end|>

---
Topic: {{ task }}
---

Generate the next single message in the conversation. Do not generate any messages as {{ chatbot_name }}.
