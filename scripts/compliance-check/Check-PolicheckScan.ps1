# Copyright (C) Microsoft Corporation.  All rights reserved.

<#
    .SYNOPSIS
        Check Policheck Scan result.
    .DESCRIPTION
        Helper script to check the Policheck result.
        If there is policheck failure, show the error and throw exception.
#>

[CmdLetbinding()]
param (
[string]$policheckResult,
[string]$raiseError = $true
)

$result = Get-Content -Path $policheckResult | Measure-Object -Line;
Write-Host("Number of errors found in this scan: " + ($result.Lines - 1));
if ($raiseError -and ($result.Lines -gt 1))
{
Get-Content -Path $policheckResult;
throw "Policheck scan completed successfully but there are issues to fix.";
}
# Read-Host "Press enter to finish the process and close this window";
