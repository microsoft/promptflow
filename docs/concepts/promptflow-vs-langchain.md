# Why build prompt flow when there is LangChain?

When we started this project, [LangChain](https://www.langchain.com/) already became popular esp. after the ChatGPT launch. One of the questions we’ve been asked is what’s the difference between prompt flow and LangChain. This article is to explain why we build it and why we design it in such way. The short answer: prompt flow is a suite of development tools for you to build LLM apps with quality, not a framework - which LangChain is.

While LLM apps are mostly in exploration stage, Microsoft started in this area a bit earlier and we’ve had the opportunity to observe how people are integrating LLMs into existing systems or build new applications. These learnings help us form our design principles. 

## 1. Prompts should be extremely visible.

It’s crystal clear that at the core of the LLM applications it’s prompts, at least for today. For a reasonably complex LLM application the majority of development work should be “tuning” your prompts (note I’m using the word “tuning” here, which we will expand further later). Any framework or tool trying to help in this space should focus on making prompt tuning easier and more straightforward. On the other hand, prompts are very volatile, you’re unlikely to write a prompt that can work across different models or even different version of same models. When you build a LLM based app, you have to understand every prompt you introduce to your application, so that you can tune it when necessary. LLM is simply not powerful or deterministic enough that you can use a prompt written by others like you use a library in any other programming language.

In this context, any design that tries to provide a smart function or agent by burying a few prompts in a library will be unlikely to work well for real-world cases. And hiding prompts inside a library’s code base only makes it’s hard for people to improve or tailor the prompts to their need.

Prompt flow, which is positioned as a tool, will not wrap any prompt in our core code base. The only place you will see prompts are our sample flows, which of course you can borrow and use. Every prompt should be written and controlled by developers, not us.

## 2. A new way of work.

LLMs are so powerful to make it much easier for developers to make their apps smarter without knowing or going through machine learning. In the meantime, LLMs make these apps more stochastic, which bring in new challenges to application development. Now you cannot simply assert “no exception” or “result == x” in your gated tests. You need to adopt new methodology and new tools for ensuring the quality of your application - i.e. a new way of work is required.

Center of the new way of work is evaluation, which is a frequent term used in machine learning space, refers to the process of assessing the performance and quality of a trained model. It involves measuring how well the model performs on a given task or dataset, and it is crucial for understanding the model's strengths, weaknesses, and overall effectiveness. Evaluation metrics and techniques vary depending on the specific task and problem domain. Some common metrics include accuracy, precision and recall, you probably already familiar with. Now the LLM apps share similar properties with machine learning models, thus requires having evaluation as the core part of development workflow - a proper set of metrics and evaluation are foundation of LLM apps quality.

Prompt flow provides tools to streamline the new way of work:

* Develop your evaluation program as Evaluation flow to calculate metrics for your app/flow, learn from our sample evaluation flows.
* Iterate your app flow, run evaluation flows via SDK/CLI on your changes and compare metrics to pick a best candidate for release. Those changes include trying different prompts, different LLM parameters like temperature etc. - this is referred as “tuning” process earlier, or sometime referred as experimentation.
* Integrate the evaluation into your CI/CD process, now the assert in your gated tests should be based on the metrics you choose.


Prompt flow introduces two concepts because of this, including:

* Evaluation flow: a flow type that indicates this flow is not for deploy or integrate into your app, it’s for evaluating an app/flow performance.
* Run: every time you run your flow with data, or run an evaluation on the output of a flow, a Run object is created to manage the history and allow for comparison and more.

While new concepts bring cognitive load, we believe it’s more critical than abstraction around different LLM APIs or vector database APIs.

## 3. Optimize for “visibility”.

There are quite some interesting application patterns emerging because of LLMs, like Retrieval Augmented Generation (RAG), ReAct and more. While how LLMs work may be elusive to many developers, how LLM apps work is not - they essentially involve a series of calls to external services such as LLMs, databases, and search engines, all glued together. Architecturally there isn’t much new, patterns like RAG and ReAct are both straightforward to implement once a developer understands what they are - plain Python programs with API calls to external services can totally serve the purpose.

By observing many internal use cases, we learned that deeper insight into the detail of the execution is critical. So having a systematic way of tracking all the interactions with external systems is one of design priority. We end up with an unconventional approach - prompt flow has a YAML file describing how function calls (we call them [Tools](../concepts/concept-tool.md)) are executed and connected into a Directed Acyclic Graph (DAG). 

Some of the key benefits of this approach are illustrated as below (visibilities!!):
1) Your flow can be nicely visualized during development and when you do test it’s clear where gets wrong. A by product is you get an architecture diagram that you can show to others.
2) Every node in the flow has it’s internal detail visualized in a consistent way.
3) You can run/debug a single node, without rerunning previous nodes. 
</b>

![promptflow-dag](../media/promptflow-dag.png)