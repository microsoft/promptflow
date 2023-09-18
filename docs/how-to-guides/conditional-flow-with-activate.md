# Create a conditional flow using activate config

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](faq.md#stable-vs-experimental).
:::

In promptflow, we support control logic by activate config, like if-else, switch. This guide will help you learn how to create a conditional flow using activate config.

## Prerequisites

Please ensure that your promptflow version is greater than `0.1.0b5`.

## Usage Description

If a node has activate config, it will only be executed when the activate condition is met. You can specify `activate.when` as flow inputs or node outputs and

::::{tab-set}
:::{tab-item} Yaml
:sync: Yaml
You can add activate config in the nodes section of flow yaml.
```yaml
activate:
  when: ${node.output}
  is: true
```
:::

:::{tab-item} VS Code Extension
:sync: VS Code Extension



:::

::::

### Yaml
### VS Code Extension

## Example flow
- If-else scenario:
- Switch scenario:


## TroubleShoot