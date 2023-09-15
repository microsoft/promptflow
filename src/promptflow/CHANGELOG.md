# Release History

## 0.1.0b7 (Upcoming)

### Bugs Fixed

- Reserve `.promptflow` folder when dump run snapshot

## 0.1.0b6 (2023.09.15)

### Features Added

- [promptflow][Feature] Store token metrics in run properties

### Bugs Fixed

- Refine error message body for flow_validator.py
- Refine error message body for run_tracker.py
- [Executor][Internal] Add some unit test to improve code coverage of log/metric
- [SDK/CLI] Update portal link to remove flight.
- [Executor][Internal] Improve inputs mapping's error message.
- [API] Resolve warnings/errors of sphinx build

## 0.1.0b5 (2023.09.08)

### Features Added

- **pf run visualize**: support lineage graph & display name in visualize page

### Bugs Fixed

- Add missing requirement `psutil` in `setup.py`

## 0.1.0b4 (2023.09.04)

### Features added

- Support `pf flow build` commands

## 0.1.0b3 (2023.08.30)

- Minor bug fixes.

## 0.1.0b2 (2023.08.29)

- First preview version with major CLI & SDK features.

### Features added

- **pf flow**: init/test/serve/export
- **pf run**: create/update/stream/list/show/show-details/show-metrics/visualize/archive/restore/export
- **pf connection**: create/update/show/list/delete
- Azure AI support:
    - **pfazure run**: create/list/stream/show/show-details/show-metrics/visualize


## 0.1.0b1 (2023.07.20)

- Stub version in Pypi.
