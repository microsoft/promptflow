With prompt flow, you can use variants to tune your prompt. In this article, you'll learn the prompt flow variants concept.

# Variants

A variant refers to a specific version of a tool node that has distinct settings. Currently, variants are supported only in the LLM tool. For example, in the LLM tool, a new variant can represent either a different prompt content or different connection settings.

Suppose you want to generate a summary of a news article. You can set different variants of prompts and settings like this:

| Variants  | Prompt                                                       | Connection settings |
| --------- | ------------------------------------------------------------ | ------------------- |
| Variant 0 | `Summary: {{input sentences}}`                               | Temperature = 1     |
| Variant 1 | `Summary: {{input sentences}}`                               | Temperature = 0.7   |
| Variant 2 | `What is the main point of this article? {{input sentences}}` | Temperature = 1     |
| Variant 3 | `What is the main point of this article? {{input sentences}}` | Temperature = 0.7   |

By utilizing different variants of prompts and settings, you can explore how the model responds to various inputs and outputs, enabling you to discover the most suitable combination for your requirements.

## Benefits of using variants 

- **Enhance the quality of your LLM generation**: By creating multiple variants of the same LLM node with diverse prompts and configurations, you can identify the optimal combination that produces high-quality content aligned with your needs.
- **Save time and effort**: Even slight modifications to a prompt can yield significantly different results. It's crucial to track and compare the performance of each prompt version. With variants, you can easily manage the historical versions of your LLM nodes, facilitating updates based on any variant without the risk of forgetting previous iterations. This saves you time and effort in managing prompt tuning history.
- **Boost productivity**: Variants streamline the optimization process for LLM nodes, making it simpler to create and manage multiple variations. You can achieve improved results in less time, thereby increasing your overall productivity.
- **Facilitate easy comparison**: You can effortlessly compare the results obtained from different variants side by side, enabling you to make data-driven decisions regarding the variant that generates the best outcomes.

## Next steps

- [Tune prompts with variants](../how-to-guides/tune-prompts-with-variants.md)