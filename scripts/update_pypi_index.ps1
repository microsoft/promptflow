#Usage indexer.ps1 configfile

param(
    [string]$config,
    [string]$local_path,
    [string]$prefix,
    [string]$channel = "test",
    [string]$suffix = ".whl"
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

function Get-Blobs($storage, $suffix)
{
    Indent
    Write-Host $([string]::Format("Get-Blobs:: Getting blobs from storage '{0}', container '{1}' with prefix '{2}' and suffix '{3}'", $storage.account, $storage.container, $prefix, $suffix))

    if ($storage.type -eq "arm")
    {
        $supress = Set-AzContext -SubscriptionName $storage.subscription -ErrorAction SilentlyContinue
        $supress = Set-AzCurrentStorageAccount -Name $storage.account -ResourceGroupName $storage.resource
    }
    else
    {
        Write-Host "...skipping because of the unsupported storage type: $__storage.type"
    }

    $__Total = 0
    $__MaxReturn = 1000000
    $__Token = $Null
    $__Blobs= $Null
    do
    {
        $__Blobs = Get-AzStorageBlob -Container $storage.container -MaxCount $__MaxReturn  -Prefix $prefix -ContinuationToken $__Token | Where-Object { ($_.ICloudBlob.Name.EndsWith($suffix)) -and (-not ($_.ICloudBlob.IsSnapshot)) }
        $__Total += $__Blobs.Count
        if($__Blobs.Length -le 0) { Break;}
        $__Token = $__Blobs[$blobs.Count -1].ContinuationToken;

    }While ($__Token -ne $Null)
    Write-Host $([string]::Format("Get-Blobs:: Found {0} blobs (excluding snapshots)", $__Blobs.Length))
    UnIndent
    $__Blobs
}


function Create-Snapshots($storage, $blobs)
{
    if ($storage.makesnapshots -eq "false")
    {
        Indent
        Write-Host $([string]::Format("Create-Snapshots:: Snapshots are not enabled. Skipping {0} blobs", $blobs.Length))
        UnIndent
        return
    }

    Indent
    Write-Host $([string]::Format("Create-Snapshots:: Creating snapshots of all {0} blobs in '{1}/{2}/{3}'", $blobs.Length, $storage.account, $storage.container, $prefix))

    if ($storage.type -eq "arm")
    {
        $supress = Set-AzContext -SubscriptionName $storage.subscription -ErrorAction SilentlyContinue
        $supress = Set-AzCurrentStorageAccount -Name $storage.account -ResourceGroupName $storage.resource
    }
    else
    {
        Write-Host "...skipping because of the unsupported storage type: $__storage.type"
    }

    foreach ($_blob in $blobs)
    {
        if ($_blob.ICloudBlob.Name -ne $null)
        {
            $__snap = $_blob.ICloudBlob.CreateSnapshot()
        }
    }
    Write-Host "Create-Snapshots:: Completed"
    UnIndent
}

function Create-Backup($storage, $blobs)
{
    if ($storage.backup -eq $Null)
    {
        Indent
        Write-Host $([string]::Format("Create-Backup:: Back-up container is not specified. Skipping {0} blobs", $blobs.Length))
        UnIndent
        return
    }
    $__folder = Get-Date -UFormat %Y_%m_%d_%H_%M_%S

    Indent
    Write-Host $([string]::Format("Create-Backup:: Creating backup of all {0} blobs in '{1}/{2}/{3}'", $blobs.Length, $storage.account, $storage.backup,$__folder))

    if ($storage.type -eq "arm")
    {
        $supress = Set-AzContext -SubscriptionName $storage.subscription -ErrorAction SilentlyContinue
        $supress = Set-AzCurrentStorageAccount -Name $storage.account -ResourceGroupName $storage.resource
    }
    else
    {
        Write-Host "...skipping because of the unsupported storage type: $__storage.type"
    }

    foreach ($_blob in $blobs)
    {
        $__blobname = [string]::Concat($prefix, $__folder, "/", $_blob.ICloudBlob.Name)
        $supress = Start-CopyAzureStorageBlob -SrcContainer $storage.container -SrcBlob $_blob.ICloudBlob.Name -DestContainer $storage.backup -DestBlob $__blobname
    }

    Write-Host "Create-Backup:: Completed"
    UnIndent
}

function New-TemporaryDirectory
{
    $__path = Join-Path ([System.IO.Path]::GetTempPath()) ([System.IO.Path]::GetRandomFileName())

    $supress = New-Item -ItemType Directory -Path $__path

    $__path
}

#function Create-Index($storages, $endpoint, $prefix, $cdn, $external)
function Create-Index($target, $storages, $external)
{
    Indent
    Write-Host $([string]::Format("Create-Index:: Creating index for {0} endpoint", $target.endpoint))

    $endpoint = $target.endpoint

    $__packages = @{}

	$__storage_list = New-Object System.Collections.ArrayList
    foreach ($storage in $storages)
    {
        $__id = $storage.type + "|" + $storage.account + "|" + $storage.resource + "|" + $storage.subscription + "|" + $storage.container+"|"+$prefix

		if ($__storage_list.Contains($__id))
		{
			continue
		}
		$supress = $__storage_list.Add($__id)

        Indent

        Write-Host $([string]::Format("Create-Index:: Looking for blobs in a location with id '{0}'", $__id))
        $__blobs = Get-Blobs $storage $suffix
        foreach ($_blob in $__blobs)
        {
            $__package_name = $_blob.ICloudBlob.Name.Substring($prefix.Length)
            if ($__package_name.Contains("/"))
            {
                continue
            }

            $__parts = $__package_name.Split('-')
            if ($target.cdnlink -eq $Null)
            {
                $__token = ""
                if ($storage.generatetoken -eq "true")
                {
                    $__token = New-AzStorageBlobSASToken -Container $storage.container -Blob $_blob.ICloudBlob.Name -Permission rl -StartTime (get-date) -ExpiryTime (get-date).AddYears(1)
                }
                if ($__packages.ContainsKey($__parts[0]))
                {
                    $__packages[$__parts[0]].Add($__package_name, $_blob.ICloudBlob.Uri.OriginalString+$__token)
                }
                else
                {
                    $__packages.Add($__parts[0], @{$__package_name = $_blob.ICloudBlob.Uri.OriginalString+$__token})
                }
            }
            else
            {
                $__cdnlink = "https://" + $target.cdnlink + "/" +$storage.Value.container + "/" + $_blob.Name
                if ($__packages.ContainsKey($__parts[0]))
                {
                    $__packages[$__parts[0]].Add($__package_name, $__cdnlink)
                }
                else
                {
                    $__packages.Add($__parts[0], @{$__package_name = $__cdnlink})
                }
            }
        }
        UnIndent
    }
    Write-Host $([string]::Format("Create-Index:: Found {0} unique package names", $__packages.Count))
    if ($local_path)
    {
		Remove-Item $local_path\* -Recurse
        $__path = $local_path
    }
    else
    {
        $__path = New-TemporaryDirectory
    }
    $__index_main = Join-Path ($__path) ("index.html")
    $supress = New-Item -ItemType File -Path $__index_main
    # Output first line as ASCII to avoid the Byte Order Mark
    "<!DOCTYPE html>" | Out-File -Filepath $__index_main -Append -Encoding ASCII
    "<html lang='en'><head><meta charset='utf-8'><meta name='api-version' value='2'/><title>Simple Index</title></head><body>" | Out-File -Filepath $__index_main -Append -Encoding utf8
    foreach ($_package in $__packages.GetEnumerator())
    {
        Indent
        Write-Host $([string]::Format("Create::Index:: Package '{0}' has {1} versions available", $_package.Key, $_package.Value.Count))
        $__normname = $_package.Key.Replace('.','-')
        $__normname = $__normname.Replace('_','-')
        $__normname = $__normname.ToLower()
        [string]::Format("<a href='https://{0}/{2}{1}'>{1}</a><br/>", $endpoint, $__normname, $prefix) | Out-File -Filepath $__index_main -Append -Encoding utf8

        $__index_item_folder = Join-Path ($__path) ($__normname)
        $__index_item = Join-Path ($__index_item_folder) ("index.html")

        if(-not (Test-Path $__index_item_folder))
        {
            $supress = New-Item -ItemType Directory -Path $__index_item_folder
            $supress = New-Item -ItemType File -Path $__index_item
        }

        "<!DOCTYPE html>" | Out-File -Filepath $__index_item -Append -Encoding ASCII
        [string]::Format("<html lang='en'><head><meta charset='utf-8'><title>{0}</title></head><body>", $__normname) | Out-File -Filepath $__index_item -Append -Encoding utf8
        foreach ($_item in $_package.Value.GetEnumerator() | Sort-Object Value -Descending)
        {
            [string]::Format("<a href='{0}' rel='external'>{1}</a><br/>", $_item.Value, $_item.Key) | Out-File -Filepath $__index_item -Append -Encoding utf8
        }
        "</body></html>" | Out-File -Filepath $__index_item -Append -Encoding utf8
        UnIndent
    }

    if ($external -ne $Null)
    {
        foreach ($member in $external.PSObject.Properties)
        {
            $__pkgname=$member.Name
            $__pkgvalue=$member.Value
            $__index_item_folder = Join-Path ($__path) ($__pkgname)
            $supress = New-Item -ItemType Directory -Path $__index_item_folder
            Invoke-WebRequest -Uri $__pkgvalue -OutFile "$__index_item_folder\index.html"
            [string]::Format("<a href='https://{0}/{2}{1}'>{1}</a><br/>", $endpoint, $__pkgname, $prefix) | Out-File -Filepath $__index_main -Append -Encoding utf8
        }
    }

    "</body></html>" | Out-File -Filepath $__index_main -Append -Encoding utf8

    Write-Host $([string]::Format("Create-Index:: Complete. Index structure: '{0}'", $__path))
    UnIndent
    $__path
}

function Refresh-Index($path, $storage)
{
    Indent
    Write-Host $([string]::Format("Refresh-Index:: Deploying index into '{0}/{1}/{2}'", $storage.account, $storage.container, $prefix))

    if ($storage.type -eq "arm")
    {
        $supress = Set-AzContext -SubscriptionName $storage.subscription -ErrorAction SilentlyContinue
        $supress = Set-AzCurrentStorageAccount -Name $storage.account -ResourceGroupName $storage.resource
    }
    else
    {
        Write-Host "...skipping because of the unsupported storage type: $__storage.type"
    }

    $__files = Get-ChildItem -Path $path -Recurse –File

    $__blobProperties = @{"ContentType" = "text/html; charset=utf-8"};

    foreach ($_file in $__files)
    {
        $__blob = [string]::Concat($prefix, $_file.FullName.Substring($path.Length + 1))
        $supress = Set-AzStorageBlobContent -File $_file.FullName -Container $storage.container -Blob $__blob -Force -Properties $__blobProperties
    }
    Write-Host "Refresh-Index:: Completed"
    UnIndent
}

if ($config -eq "")
{
    Write-Error "No config specified"
    return -1
}

try
{
    Write-Host "Starting AzureML PyPi index update"

    Write-Host $([string]::Format("Selected target: {0}", $config))
    $__config = Get-Target $config

    $_release = $__config.releases.PSObject.Properties[$channel].Value
    $target = $__config.targets.PSObject.Properties[$_release.index].Value

    Write-Host "Getting current target index"
    $_blobs = Get-Blobs $target ".html"

    Write-Host "Creating backups for current target index"
    #Create back-up in a snapshot container
    $supress = Create-Backup $target $_blobs

    #Create azure blob snapshots (easier to roll back, prevents from deleting)
    $supress = Create-Snapshots $target $_blobs

    $storages = New-Object System.Collections.ArrayList
    $storages.Add($__config.targets.PSObject.Properties[$_release.package_repo].Value)
    if ($_release.package_repo -ne $_release.extensions_repo)
    {
        $storages.Add($__config.targets.PSObject.Properties[$_release.extensions_repo].Value)
    }

    Write-Host "Updating index"
    #Generate index from the sources
    $index_path = Create-Index $target $storages $_release.external
    #Refresh index
    Refresh-Index $index_path $target
    Write-Host "Finished"
}
catch
{
   Write-Error $_.Exception
   return -2
}
return 0
