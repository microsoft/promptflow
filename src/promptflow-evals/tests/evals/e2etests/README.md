# E2E tests logging to the application insights.
For the regression tracking we are recording test run times and estimate the installation times of promptflow-evals wheel with and without `azure` optional dependency. The table below summarizes the events we are logging.

## Events
| Event | Description | Logging value | Is recorded |
|-------|-------------|---------------|-------------|
| install_promptflow_no_extras | Installation time of the packages without Azure | The number of packages installed and installation time in seconds | N/A |
| install_promptflow_with_extras | Installation time of the packages with Azure | The number of packages installed and installation time in seconds | N/A |
| run_e2e_tests_local | Run time tests marked as `localtest`\*. Each test is being logged as `TestClass::test_name`. | The test run time in seconds | Yes |
| run_e2e_tests_azure | Run time tests marked as `azuretest`\*. Each test is being logged as `TestClass::test_name`. These tests write tracking information to Azure. | The test run time in seconds | Yes |
| performance_tests | Run tests marked as `performance_test` Each test is being logged as `TestClass::test_name`. These tests write tracking information to Azure. | The test run time in seconds | No |

\* `localtest` is used to mark the whole class, while `azuretest` can be used to only mark tests that need `promptflow-azure` package. `performance_test` tests can mark both class and the method of class. It is not excluive with `localtest` or `azuretest`.

## Sample query
The next query demonstrates the selection of installation times of promptflow-evals without additional dependencies for time after 2024-07-02 and plotting averges for different dates and operation systems. [Application insights, used for logging](https://ms.portal.azure.com/#@microsoft.onmicrosoft.com/resource/subscriptions/96aede12-2f73-41cb-b983-6d11a904839b/resourceGroups/promptflow-sdk/providers/microsoft.insights/components/promptflow-sdk/overview).

```
let date_of_run=datetime("2024-07-02");
let event='install_promptflow_no_extras';
customEvents
| where timestamp > date_of_run
| where name == event
| extend parsed = parse_json(customDimensions)
| project 
      name,
      run_date=format_datetime(timestamp, 'yyyy-MM-dd'),
      metric = parsed['activity_name'],
      OS = strcat(parsed["OS"], "_", parsed["OS_release"]),
      python_version = tostring(parsed['python_version']),
      install_time_s=todecimal(parsed["install_time_s"])
| summarize install_time_s = avg(install_time_s) by run_date, OS //python_version, stdev=stdev(value)
| order by run_date asc
| render columnchart with(
    kind=unstacked
)
```