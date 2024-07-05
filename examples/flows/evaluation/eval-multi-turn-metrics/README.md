# Evaluation multi turn metrics:

This evaluation flow will evaluate a conversation by using Large Language Models (LLM) to measure the quality of the responses.

## What you will learn

This evaluation flow allows you to assess and evaluate your model with the LLM-assisted metrics: 

* __grounding__: Measures whether the answer follows logically from the information contained in the context based on provided answer and context. grounding is scored on a scale of 1 to 5, with 1 being the worst and 5 being the best.

* __answer_relevance__: Measure whether the answer is relevance to the question based on provided question, context and answer. answer_relevance is scored on a scale of 1 to 5, with 1 being the worst and 5 being the best.

* __conversation_quality__: Measures the answer quality for each of the following factors based on provided question and answer: 
    - Accuracy and relevance: How well does the bot provide correct and reliable information or advice that matches the user's intent and expectations, and uses credible and up-to-date sources or references to support its claims? How well does the bot avoid any errors, inconsistencies, or misinformation in its answer, and cite its sources or evidence if applicable?
    - Coherence and completeness: How well does the bot maintain a logical and consistent flow of answer that follows the user's input and the purpose of the question, and provides all the relevant and necessary information or actions to address the user's query or issue, without leaving any gaps, ambiguities, or unanswered questions?
    - Engagement and tone: How well does the bot capture and maintain the user's interest and attention, and motivate them to continue the conversation or explore the topic further, using natural and conversational language, personality, and emotion? how well does the bot's tone match or adapt to the user's tone and mood? Does the bot avoid being rude, sarcastic, condescending, or too formal or informal, and convey respect, empathy, and politeness?
    - Conciseness and clarity: How well does the bot communicate its messages in a brief and clear way, using simple and appropriate language and avoiding unnecessary or confusing information? How easy is it for the user to understand and follow the bot responses, and how well do they match the user's needs and expectations?
    - Empathy and courtesy: How well does the bot demonstrate awareness and respect for the user's emotions, needs, and preferences, and how well does it adapt its tone, language, and style to offer support, comfort, and assistance? Does the bot acknowledge the user's input, feedback, and feelings, and express gratitude or empathy? Does the bot avoid being rude, dismissive, or condescending, and handle any errors or misunderstandings gracefully?
    - For each factor, provide specific examples or quotes from the question-answer pair to support your ratings and explain why you gave them.
    - Give an score value which is calculated by ( 0.3 * "accuracy and relevance" + 0.2 * "coherence and completeness" + 0.25 * "engagement and tone" + 0.15 * "conciseness and clarity" + 0.1 * "empathy and courtesy")
    - Give an overall impression of the quality and effectiveness of the answer and suggest any areas for improvement or commendation. Write it in "Overall".

    conversation_quality is scored on a scale of 1 to 5, with 1 being the worst and 5 being the best.

* __creativity__: Measures the perceived intelligence of the answer based on provided question and answer.
    - Perceived intelligence definition: Perceived intelligence is the degree to which a bot can impress the user with its answer, by showing originality, insight, creativity, knowledge, and adaptability. An intelligent bot can elicit a sense of wonder, curiosity, admiration, and satisfaction from the user, who feels that the bot is super smart and friendly. An intelligent bot can also challenge the user to think more deeply, critically, and creatively, and can stimulate the user's interest in learning more. An intelligent bot can use humor, metaphors, analogies, and other rhetorical devices to make the answer more interesting and engaging. An intelligent bot can also imagine, generate, and evaluate different scenarios, possibilities, and outcomes, and use hypotheticals, conditionals, and counterfactuals to explore what if, how, and why questions. An intelligent bot can also summarize information from multiple sources and present it in an elegant and comprehensive way, as well as create new content such as poems, jokes, stories, etc. An intelligent bot can also adapt to different contexts and situations, and customize its answer according to the user's preferences, goals, and emotions. Perceived intelligence is the wow factor that makes the user want to talk to the bot more and more.
    Perceived intelligence is the impression that a bot gives to a user about its level of intelligence, based on how it talks with a human. Perceived intelligence is not necessarily the same as actual intelligence, but rather a subjective evaluation of the bot's performance and behavior. Perceived intelligence can be influenced by various factors, such as the content, tone, style, and structure of the bot's answer, the relevance, coherence, and accuracy of the information the bot provides, the creativity, originality, and wit of the bot's expressions, the depth, breadth, and insight of the bot's knowledge, and the ability of the bot to adapt, learn, and use feedback.
    Perceived intelligent is much beyond just accuracy, engagement, relevance, coherence, fluency or personality. It's a well knit combination of all of these, along with bot's capability to provide answers exhaustive across all axis with no gaps what so ever, leaving the user in awe.
    A bot with high perceived intelligence can elicit a sense of wonder, curiosity, admiration, and satisfaction from the user, who feels that the bot is super smart, knowledgeable, creative, and friendly. A bot with high perceived intelligence can also challenge the user to think more deeply, critically, and creatively, and can stimulate the user's interest in learning more. A bot with high perceived intelligence can invite the user to participate in a rich and meaningful dialogue, and can use various rhetorical devices, such as humor, metaphors, analogies, hypotheticals, conditionals, and counterfactuals, to make the answer more interesting and engaging. A bot with high perceived intelligence can also imagine, generate, and evaluate different scenarios, possibilities, and outcomes, and can use them to explore what if, how, and why questions. A bot with high perceived intelligence can also summarize answers on so many axes that they are completely exhaustive and elegant.
    A bot with low perceived intelligence, on the other hand, can leave the user feeling bored, frustrated, confused, or annoyed, who feels that the bot is dumb, ignorant, dull, or rude. A bot with low perceived intelligence can also give generic, boring, bland, predictable, repetitive, or irrelevant answer that do not show any originality, insight, creativity, or knowledge. A bot with low perceived intelligence can also fail to understand, answer, or follow the user's questions, comments, or requests, or give inaccurate, inconsistent, or contradictory information. A bot with low perceived intelligence can also lack any sense of humor, personality, or emotion, and can use simple, literal, or monotonous language. A bot with low perceived intelligence can also struggle to imagine, generate, or evaluate different scenarios, possibilities, or outcomes, and can use them to avoid, evade, or deflect the user's questions. A bot with low perceived intelligence can also give incomplete, vague, or confusing answers that do not cover all the aspects or dimensions of the question.

    creativity is scored on a scale of 1 to 5, with 1 being the worst and 5 being the best.

## Prerequisites

- Connection: Azure OpenAI or OpenAI connection.
    > !Note: Recommend to use `gpt-4` series models than the `gpt-3.5` for better performance.
    > !Note: Recommend to use `gpt-4` model (Azure OpenAI `gpt-4` model with version `0613` or later) than `gpt-4-turbo` model (Azure OpenAI `gpt-4` model with version `1106` or later) for better performance. Due to inferior performance of `gpt-4-turbo` model, when you use it, sometimes you might need to set the `response_format`to {"type":"json_object"} for these nodes: conversation_quality, creativity, answer_relevance, in order to make sure the llm can generate valid json response.

## Tools used in this flow
- LLM tool
- Python tool
- Prompt tool


## 0. Setup connection
Prepare your Azure OpenAI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>
```

## 1. Test flow/node
```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .
```