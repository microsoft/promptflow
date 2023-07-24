param(
    [string]$config,
    [string]$source,
    [string]$prefix,
    [bool]$uploadaslatest = $false,
    [bool]$overridewheel = $true,
    [string]$channel = "test"
)

if ($global:__indent__ -eq $null)
{
    $global:__indent__=0
}

function Write-Host
{
    Microsoft.PowerShell.Utility\Write-Host (' ' * $global:__indent__) -NoNewline
    & 'Microsoft.PowerShell.Utility\Write-Host' $args
}

function Indent
{
    $global:__indent__+=4
}

function UnIndent
{
    $global:__indent__ -= 4
    if ($global:__indent__ -lt 0)
    {
        $global:__indent__ = 0
    }
}

function Get-Target($config)
{
    Get-Content -Raw -Path $config | ConvertFrom-Json
}

# Examples:
# ml-0.0.83-py3-none-any.whl -> ml-latest-py3-none-any.whl
# azure_ml-0.0.83-py3-none-any.whl -> azure_ml-latest-py3-none-any.whl
function Override-Version-With-Latest($name)
{
    return $name -replace "-([0-9.]*)-","-latest-"
}

function Upload-Package($storage, $source, $package)
{
    Indent
    if ($package -eq "promptflow")
    {
        $package = "promptflow-sdk"
    }
    elseif ($package -eq "embeddingstore")
    {
        $package = "embeddingstore-sdk"
    }
    elseif ($package -eq "promptflow-pypi")
    {
        $package = "promptflow"
    }
    $__file = Get-ChildItem -Path $source -Filter "$package/dist/*.whl" -Name | Select-Object -First 1

    if ($uploadaslatest -eq $false)
    {
        $__destfilename = $__file
    }
    else
    {
        $__destfilename = Override-Version-With-Latest($__file)
    }
    $__blob = [string]::Concat($prefix, $__destfilename)
    Write-Host "Uploading $__file to $__blob"

    $__text = Get-Content "$source/$package/dist/$__file" -AsByteStream -Raw
    $__md5 = New-Object -TypeName System.Security.Cryptography.MD5CryptoServiceProvider

    $__hash = [System.Convert]::ToBase64String($__md5.ComputeHash($__text))

    $__existingblod = Get-AzStorageBlob -Container $storage.container -Blob $__blob -ErrorAction SilentlyContinue
    $__hashblob =  $__existingblod.ICloudBlob.Properties.ContentMD5

    if (-not [string]::IsNullOrEmpty($__hashblob) -and $overridewheel -eq $false)
    {
        $existing_blobname = $__existingblod.Name
        Write-Error "Cannot override wheel: $existing_blobname" -ErrorAction Stop
    }

    Write-Host "Comparing hash $__hash  -=vs=-  $__hashblob"
    if ($__hash -eq $__hashblob)
    {
        Write-Host "...skipping because of the same contentmd5"
    }
    else
    {
        $supress = Set-AzStorageBlobContent -Container $storage.container -File "$source/$package/dist/$__file" -Blob $__blob -Force
    }
    UnIndent
}

Write-Host $([string]::Format("Selected target: {0}", $config))
$__config = Get-Target $config

Write-Host $([string]::Format("Selected channel: {0}", $channel))
$_release = $__config.releases.PSObject.Properties[$channel].Value

Write-Host $([string]::Format("Selected package repo: {0}", $_release.package_repo))
$__storage = $__config.targets.PSObject.Properties[$_release.package_repo].Value

if ($__storage.type -eq "arm")
{
    $supress = Set-AzContext -SubscriptionName $__storage.subscription -ErrorAction SilentlyContinue
    $supress = Set-AzCurrentStorageAccount -Name $__storage.account -ResourceGroupName $__storage.resource
}
else
{
    Write-Host "...skipping because of the unsupported storage type: $__storage.type"
}

Write-Host $([string]::Format("Uploading packages into '{2}' container with prefix {3} in storage '{0}' in '{1}' subscription", $__storage.account, $__storage.subscription, $__storage.container, $__storage.prefix))

foreach ($package in $_release.packages)
{
    Write-Host $([string]::Format("Uploading package: {0}", $package))
    $supress = Upload-Package $__storage $source $package
}

$__storage = $__config.targets.PSObject.Properties[$_release.index].Value


if ($__storage.type -eq "arm")
{
    $supress = Set-AzContext -SubscriptionName $__storage.subscription -ErrorAction SilentlyContinue
    $supress = Set-AzCurrentStorageAccount -Name $__storage.account -ResourceGroupName $__storage.resource
}
else
{
    Write-Host "...skipping because of the unsupported storage type: $__storage.type"
}

Write-Host $([string]::Format("Uploading extensions into '{2}' container with prefix {3} in storage '{0}' in '{1}' subscription", $__storage.account, $__storage.subscription, $__storage.container, $__storage.prefix))

foreach ($extension in $_release.extensions)
{
    Write-Host $([string]::Format("Uploading extension: {0}", $extension))
    $supress = Upload-Package $__storage $source ($extension + "/src/machinelearningservices")
}

return 0
