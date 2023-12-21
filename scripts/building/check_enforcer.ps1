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

#>
[CmdletBinding()]
param(
    [string]$MergeCommit = "",
    [int]$LoopTimes = 30 # Loop for 15 minutes at most.

)

$github_repository = 'microsoft/promptflow'
$snippet_debug = 1 # Write debug info to console.


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

    # Basic fact of sdk cli checked pipelines
    # update this number if we expand the matrix of pipeline
    # sdk_cli_tests: 4 runs
    # sdk_cli_global_config_tests: 1 run
    # sdk_cli_azure_test: 4 runs
    $pipelines = @{
        "sdk_cli_tests" = 4;
        "sdk_cli_global_config_tests" = 1;
        "sdk_cli_azure_test" = 4;
    }
    $pipelines_count = @{
        "sdk_cli_tests" = 0;
        "sdk_cli_global_config_tests" = 0;
        "sdk_cli_azure_test" = 0;
    }

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
    $pipelines = @{
        "sdk_cli_tests" = 4;
        "sdk_cli_global_config_tests" = 1;
        "sdk_cli_azure_test" = 4;
    }

    $pipelines_success_count = @{
        "sdk_cli_tests" = 0;
        "sdk_cli_global_config_tests" = 0;
        "sdk_cli_azure_test" = 0;
    }
    
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

function run_checks() {

    $need_to_check = New-Object System.Collections.Generic.HashSet[string]
    git diff --name-only HEAD origin/main | ForEach-Object {
        if ($snippet_debug -eq 1) {
            Write-Output "git diff --name-only HEAD main $_"
        }
        if ($_.Contains("src/promptflow/")) {
            $need_to_check.Add("sdk_cli")
        }
    }

    $sdk_cli_check = $false

    foreach ($item in $need_to_check) {
        if ($item -eq "sdk_cli") {
            $sdk_cli_check = $true
        }
    }

    $failed_reason =  ""
    $not_started_counter = 5
    
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
