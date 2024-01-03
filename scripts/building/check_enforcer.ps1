<#
.DESCRIPTION
Enforce the check of pipelines.

There are a few places that need to be updated when adding new pipelines.
1. This script will get diff of current branch and main branch.
   If the diff contains your concerned files, please add $need_to_check variable.
2. To Enable more pipelines, following the code of sdk_cli_trigger_checks and sdk_cli_checks.
   Create new functions and add them to run_checks.

.EXAMPLE
PS> ./check_enforcer.ps1
PS> ./check_enforcer.ps1 -MergeCommit <git_commit_sha> -LoopTimes 30
PS> ./check_enforcer.ps1 -GithubWorkspace <path_to_promptflow>

#>
[CmdletBinding()]
param(
    [string]$MergeCommit = "",
    [int]$LoopTimes = 30, # Loop for 15 minutes at most.
    [string]$GithubWorkspace = "~/promptflow/"
)

$github_repository = 'microsoft/promptflow'
$snippet_debug = 1 # Write debug info to console.

# Special cases for pipelines that need to be triggered more or less than default value 1.
# If 0, the pipeline will not be ignored in check enforcer.
$special_care = @{
    "sdk_cli_tests" = 4;
    "sdk_cli_azure_test" = 4;
}

# copy from original yaml pipelines
$checks = @{
    "sdk_cli_tests" = @("src/promptflow/**", "scripts/building/**", ".github/workflows/promptflow-sdk-cli-test.yml")
    "sdk_cli_global_config_tests" = @("src/promptflow/**", "scripts/building/**", ".github/workflows/promptflow-global-config-test.yml")
    "sdk_cli_azure_test" = @("src/promptflow/**", "scripts/building/**", ".github/workflows/promptflow-sdk-cli-azure-test.yml")
}

$reverse_checks = @{}
$pipelines = @{}
$pipelines_count = @{}


if ($MergeCommit -eq "") {
    git log -1 | ForEach-Object {
        if ($_.Contains("Merge")) {
            $MergeCommit = $_.Split(" ")[-3]
        }
    }

    if ($snippet_debug -eq 1) {
        Write-Output "MergeCommit $MergeCommit"
    }
}

function sdk_cli_trigger_checks([ref]$failed_reason_ref, [ref]$valid_status_array_ref) {
    # Check if all sdk cli pipelines are triggered.
    # return all valid checks when successful
    $failed_reason_ref.Value = ""

    $(gh api /repos/$github_repository/commits/$MergeCommit/check-suites) `
    | ConvertFrom-Json `
    | Select-Object -ExpandProperty check_suites `
    | ForEach-Object {
        if ($snippet_debug -eq 1) {
            Write-Output "check-suites id $($_.id)"
        }
        $suite_id = $_.id
        $(gh api /repos/$github_repository/check-suites/$suite_id/check-runs) `
        | ConvertFrom-Json `
        | Select-Object -ExpandProperty check_runs `
        | ForEach-Object {
            if ($snippet_debug -eq 1) {
                Write-Output "check runs name $($_.name)"
            }
            foreach ($key in $pipelines.Keys) {
                $value = $pipelines[$key]
                if ($value -eq 0) {
                    continue
                }
                if ($_.name.Contains($key)) {
                    $pipelines_count[$key] += 1
                    $valid_status_array_ref.Value += $_
                }
            }
        }
    }
    # Get pipelines of commit. count should match.
    foreach ($key in $pipelines.Keys) {
        if ($pipelines_count[$key] -lt $pipelines[$key]) {
            $failed_reason_ref.Value = "Not all pipelines are triggered."
        }
    }
}
function sdk_cli_checks([ref]$failed_reason_ref, $valid_status_array) {
    $failed_reason_ref.Value = ""
    # Basic fact of sdk cli checked pipelines

    $valid_status_array `
    | ForEach-Object {
        foreach ($key in $pipelines.Keys) {
            $value = $pipelines[$key]
            if ($value -eq 0) {
                continue
            }
            if ($_.name.Contains($key)) {
                if ($_.conclusion -ieq "success") {
                    $pipelines_success_count[$key] += 1
                } elseif ($_.conclusion -ieq "failure") {
                    $failed_reason_ref.Value = "Required pipelines are not successful."
                } else {
                    if ($failed_reason_ref.Value -eq "") {
                        $failed_reason_ref.Value = "Required pipelines are not finished."
                    }
                }
            }
            Write-Output "$($_.name) is $($_.conclusion)."
        }
    }
}

function trigger_prepare($input_paths, [ref]$failed_reason_ref) {
    foreach ($input_path in $input_paths) {
        if ($checks.ContainsKey("samples_connections_connection")) {
            continue
        }
        if ($input_path.Contains("examples") -or $input_path.Contains("samples")) {
            # Define the input path
            Push-Location $GithubWorkspace
            $pipelines_samples = (python $GithubWorkspace\scripts\readme\readme.py -c | ConvertFrom-Json)
            Pop-Location
            $failed_reason_ref.Value = (git diff-index --quiet HEAD -- || "Run readme generation before check in")
            if ($failed_reason_ref.Value -ne "") {
                return
            }
            # merge piplines_samples to checks
            foreach ($key in $pipelines_samples.Keys) {
                $value = $pipelines_samples[$key]
                $checks[$key] = $value
            }
        }
    }
    # reverse checks
    foreach ($key in $checks.Keys) {
        $value = $checks[$key]
        foreach ($path in $value) {
            if ($reverse_checks.ContainsKey($path)) {
                $reverse_checks[$path] += $key
            } else {
                $reverse_checks[$path] = @($key)
            }
        }
    }
    # render $pipelines and $pipelines_count using $input_paths
    foreach ($input_path in $input_paths) {
        # input pattern /**: input_path should match in the middle
        # input pattern /*: input_path should match last but one
        # other input pattern: input_path should match last
        $keys = $reverse_checks.Keys
        $keys = $keys | Where-Object { (python $GithubWorkspace\scripts\building\fnmatch.py -g $_ -f $input_path) -eq "True" }
        # $reverse_checks.Keys and $keys
        foreach ($key_item in $keys) {
            foreach ($key in $reverse_checks[$key_item]) {
                if ($pipelines.ContainsKey($key)) {
                    if ($special_care.ContainsKey($key)) {
                        $pipelines[$key] = $special_care[$key]
                    } else {
                        $pipelines[$key] = 1
                    }
                }
                $pipelines_count[$key] = 0
            }
        }
    }
}

function run_checks() {
    Push-Location $GithubWorkspace
    $input_paths = git diff --name-only HEAD origin/main
    Pop-Location

    $failed_reason =  ""
    $not_started_counter = 5

    # Prepare how many pipelines should be triggered.
    trigger_prepare $input_paths ([ref]$failed_reason)
    if ($failed_reason -ne "") {
        throw "$failed_reason"
    }

    for ($i = 0; $i -lt $LoopTimes; $i++) {
        Start-Sleep -Seconds 30

        $failed_reason = ""
        $valid_status_array = @()

        # Get all triggered pipelines.
        # If not all pipelines are triggered, continue.
        if ($sdk_cli_check -eq $true) {
            sdk_cli_trigger_checks ([ref]$failed_reason) ([ref]$valid_status_array)
        }
        if ($failed_reason -ne "") {
            if ($not_started_counter -eq 0) {
                throw "$failed_reason for 6 times."
            }
            Write-Output "$failed_reason"
            $not_started_counter -= 1
            continue
        }

        # Get pipeline conclusion Priority:
        # 1. Not successful, Fail.
        # 2. Not finished, Continue.
        # 3. Successful, Break.
        if ($sdk_cli_check -eq $true) {
            sdk_cli_checks ([ref]$failed_reason) $valid_status_array
        }

        if ($failed_reason.Contains("not successful", [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "$failed_reason"
        } elseif ($failed_reason.Contains("not finished", [System.StringComparison]::OrdinalIgnoreCase)) {
            Write-Output "$failed_reason"
            continue
        } else {
            Write-Output "All required pipelines are successful."
            break
        }
    }
    if ($failed_reason -ne "") {
        throw "$failed_reason"
    }
}

run_checks
