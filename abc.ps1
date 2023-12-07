$first_commit = 'yigao/abc' # github.sha
$diff_commit = 'main'
$github_repository = 'microsoft/promptflow'
$first_commit_hash = 'a1bfd6865ac8a52a0af9f8a3c723055e287f9780' #git rev-parse $first_commit


function get_diffs() {

    $need_to_check = New-Object System.Collections.Generic.HashSet[string]
    git diff --name-only $first_commit $diff_commit | ForEach-Object {
        if ($_ -icontains "src/promptflow") {
            $need_to_check.Add("sdk_cli")
        }
    }

    function check_conclusion {
        param(
            [string]$conclusion
        )
        
    }

    $failed_reason =  ""
    $failedCount = 3

    for ($i = 0; $i -lt $failedCount; $i++) {
        Start-Sleep -Seconds 20
        
        $pipelines = @{
            "executor_e2e_tests" = 0;
            "executor_unit_tests" = 0;
            "sdk_cli_tests" = 0;
            "sdk_cli_global_config_tests" = 0;
            "sdk_pfs_e2e_test" = 0;
            "sdk_cli_azure_test" = 0;
        }
        $pipelines_count = @{
            "executor_e2e_tests" = 0;
            "executor_unit_tests" = 0;
            "sdk_cli_tests" = 0;
            "sdk_cli_global_config_tests" = 0;
            "sdk_pfs_e2e_test" = 0;
            "sdk_cli_azure_test" = 0;
        }
        
        foreach ($item in $need_to_check) {
            if ($item -eq "sdk_cli") {
                $pipelines.sdk_cli_tests = 2
                $pipelines.sdk_cli_global_config_tests = 2
                $pipelines.sdk_cli_azure_test = 2
                $pipelines.sdk_pfs_e2e_test = 2
            }
        }

        # Get pipeline status.
        $valid_status_array = $(gh api /repos/$github_repository/commits/$first_commit_hash/check-runs) `
        | ConvertFrom-Json `
        | Select-Object -ExpandProperty check_runs `
        | Where-Object {
            for ($j = 0; $j -lt $pipelines.Keys.Count; $j++) {
                # remove those pipelines that are not required.
                if ($pipelines[$pipelines.Keys[$j]] -eq 0) {
                    return $false
                }
                # count the number of pipelines that are required.
                if ($_.name.Contains($pipelines.Keys[$j])) {
                    $pipelines_count[$pipelines.Keys[$j]] += 1
                    return $true
                }
            }
            return $false
        }

        # Get pipeline conclusion. count should match.

        for ($j = 0; $j -lt $pipelines.Keys.Count; $j++) {
            if ($pipelines_count[$pipelines.Keys[$j]] -lt $pipelines[$pipelines.Keys[$j]]) {
                $failed_reason = "Not all pipelines are triggered."
            }
        }
        if ($failed_reason -ne "") {
            Write-Host $failed_reason
            continue
        }
        $pipelines_success_count = @{
            "executor_e2e_tests" = 0;
            "executor_unit_tests" = 0;
            "sdk_cli_tests" = 0;
            "sdk_cli_global_config_tests" = 0;
            "sdk_pfs_e2e_test" = 0;
            "sdk_cli_azure_test" = 0;
        }

        $valid_status_array `
        | ForEach-Object {
            for ($j = 0; $j -lt $pipelines.Keys.Count; $j++) {
                # remove those pipelines that are not required.
                if ($pipelines[$pipelines.Keys[$j]] -eq 0) {
                    continue
                }
                # count the number of pipelines that are required.
                if ($_.name.Contains($pipelines.Keys[$j])) {
                    if ($_.conclusion -ieq "success") {
                        $pipelines_success_count[$pipelines.Keys[$j]] += 1
                    } elseif ($_.conclusion -ieq "failure") {
                        $failed_reason = "Required pipelines are not successful."
                    } else {
                        $failed_reason = "Required pipelines are not finished."
                    }
                }
            }
        }
        if ($failed_reason.Contains("not successful")) {
            Write-Host $failed_reason
            break
        } elseif ($failed_reason.Contains("not successful")) {
            Write-Host $failed_reason
            continue
        } else {
            Write-Host "All required pipelines are successful."
            break
        }
    }
}

get_diffs