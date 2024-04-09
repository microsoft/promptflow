## 1.1.0 (Upcoming)

### Features Added
- [SDK/CLI] Save a callable class or a function as a flex flow:
  - CLI: Support `pf flow save --path <target-flow-directory> --entry hello:Hello --code ./src` to create
    a flex flow in target flow directory with specified entry.
  - SDK: Support `pf.flows.save(path=<target-flow-directory>, entry="hello:Hello", code="./src")` to create
    a flex flow in target flow directory with specified entry.
  - SDK: Support `pf.flows.infer_signature(entry=Hello)` to infer the signature of a callable class or a function.
