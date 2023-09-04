# Build a flow

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](faq.md#stable-vs-experimental).
:::

From this document, customer can build a local flow into a sharable flow along with its dependencies. 
The command is as below and customer may use `--format` to specify the format they want to build the flow into.

::::{tab-set}
:::{tab-item} CLI
:sync: CLI

```bash
# Create a flow
pf flow build --source <flow-path> --output <output-path> --format docker
```
:::
::::

Structure of output folder:
- **flow/xxx**: The flow flow without variants and additional includes.
- **.connections/xxx.yaml**: It contains all package tools meta that references in `flow.dag.yaml`.
- **Sharable files according to build format**

## Build flow as docker

- **Dockerfile**: The Dockerfile for the sharable flow.

## Build flow as executable [TBD]

## Next steps

- [Deploy a flow](./deploy-a-flow/index.md)