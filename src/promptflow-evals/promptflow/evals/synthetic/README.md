# QA.py Usage Guide

This document provides instructions on how to use `qa.py`.

## Prerequisites

Ensure you have Python installed on your system. If not, you can download it from [here](https://www.python.org/downloads/).

## Installation

Install the `promptflow-evals` extra while installing promptflow.

## Usage
Set the values for `AZURE_OPENAI_API_KEY` and `AZURE_OPENAI_ENDPOINT` in the env or update this script:

```
import os
from promptflow.evals.synthetic.qa import QADataGenerator, QAType, OutputStructure

os.environ["AZURE_OPENAI_API_KEY"] = ""
os.environ['AZURE_OPENAI_ENDPOINT'] = ""

model_name = "gpt-4"

model_config = dict(
    deployment=model_name,
    model=model_name,
    max_tokens=2000,
)

qa_generator = QADataGenerator(model_config=model_config)

import wikipedia

wiki_title = wikipedia.search("Leonardo da vinci")[0]
wiki_page = wikipedia.page(wiki_title)
text = wiki_page.summary[:700]

qa_type = QAType.CONVERSATION

result = qa_generator.generate(text=text, qa_type=qa_type, num_questions=5)

for question, answer in result["question_answers"]:
    print(f"Q: {question}")
    print(f"A: {answer}")

```

This should print out something like:

```
Q: Who was Leonardo di ser Piero da Vinci?
A: Leonardo di ser Piero da Vinci was an Italian polymath of the High Renaissance who was active as a painter, draughtsman, engineer, scientist, theorist, sculptor, and architect.

Q: When was he born and when did he die?
A: Leonardo da Vinci was born on 15 April 1452 and died on 2 May 1519.

Q: What did he become known for besides his achievements as a painter?
A: Besides his achievements as a painter, Leonardo da Vinci has also become known for his notebooks, in which he made drawings and notes on a variety of subjects, including anatomy, astronomy, botany, cartography, painting, and paleontology.

Q: How is he regarded in terms of the Renaissance humanist ideal?
A: Leonardo da Vinci is widely regarded to have been a genius who epitomized the Renaissance humanist ideal.

Q: How significant are his collective works to later generations of artists?
A: Leonardo da Vinci's collective works comprise a contribution to later generations of artists matched only by that of his younger contemporary Michelangelo.
```
