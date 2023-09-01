<#
.DESCRIPTION
Script to deploy promptflow to Azure App Service.

.PARAMETER path
The folder path to be deployed
.PARAMETER image_tag
The container image tag.
.PARAMETER registry
The container registry name, for example 'xx.azurecr.io'.
.PARAMETER name
The app name to produce a unique FQDN as AppName.azurewebsites.net.
.PARAMETER location
The app location, default to 'centralus'.
.PARAMETER sku
The app sku, default to 'F1'(free).
.PARAMETER resource_group
The app resource group.
.PARAMETER subscription
The app subscription, default using az account subscription.
.PARAMETER verbose
verbose mode.

.EXAMPLE
PS> .\deploy.ps1 -Path <folder-path> -name my_app_23d8m -i <image_tag> -r <registry> -n <app_name> -g <resource_group>
.EXAMPLE
PS> .\deploy.ps1 -Path <folder-path> -name my_app_23d8m -i <image_tag> -r <registry> -n <app_name> -g <resource_group> -Subscription "xxxx-xxxx-xxxx-xxxx-xxxx" -Verbose
#>
[CmdletBinding()]
param(
    [string]$Path,
    [Alias("i", "image_tag")][string]$ImageTag,
    [Alias("r")][string]$Registry,
    [Alias("n")][string]$Name,
    [Alias("l")][string]$Location = "eastus",
    [string]$Sku = "F1",
    [Alias("g", "resource_group")][string]$ResourceGroup,
    [string]$Subscription
)

####################### Validate args ############################
$ErrorActionPreference = "Stop"

# fail if image_tag not provided
if (!$ImageTag) {
    Write-Host "***************************"
    Write-Host "* Error: image_tag is required.*"
    Write-Host "***************************"
    exit 1
}

# check if : in image_tag
if (!$ImageTag.Contains(":")) {
    version="v$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    image_tag="${ImageTag}:${version}"
}

Write-Host "image_tag: $ImageTag"

# fail if Registry not provided
if (!$Registry) {
    Write-Host "***************************"
    Write-Host "* Error: registry is required.*"
    Write-Host "***************************"
    exit
}

# fail if name not provided
if (!$Name) {
    Write-Host "***************************"
    Write-Host "* Error: name is required.*"
    Write-Host "***************************"
    exit
}

# fail if resource_group not provided
if (!$ResourceGroup) {
    Write-Host "***************************"
    Write-Host "* Error: resource_group is required.*"
    Write-Host "***************************"
    exit
}

# fail if image_tag not provided
if (!$Path) {
    Write-Host "***************************"
    Write-Host "* Error: Path is required.*"
    Write-Host "***************************"
    exit 1
}

####################### Build and push image ############################
Write-Host "Change working directory to $Path"
cd $Path
docker build -t "$ImageTag" .

if ($Registry.Contains("azurecr.io")) {
    Write-Host "Trying to login to $Registry..."
    az acr login -n "$Registry"

    $AcrImageTag = $Registry + "/" + $ImageTag
    Write-Host "ACR image tag: $AcrImageTag"
    docker tag "$ImageTag" "$AcrImageTag"
    $ImageTag = $AcrImageTag
}
else {
    Write-Host "Make sure you have docker account login!!!"
    printf "***************************************************\n"
    printf "* WARN: Make sure you have docker account login!!!*\n"
    printf "***************************************************\n"

    $DockerImageTag = $Registry + "/" + $ImageTag

    Write-Host "Docker image tag: $DockerImageTag"
    docker tag "$ImageTag" "$DockerImageTag"
    $ImageTag = $DockerImageTag
}

Write-Host "Start pushing image...$ImageTag"
docker push "$ImageTag"

####################### Create and config app ############################

function Append-To-Command {
    param (
        [string] $Command
    )
  if ($Subscription) {
        $Command = "$Command --subscription $Subscription"
  }
  if ($VerbosePreference -eq "Continue") {
        $Command="$Command --debug"
  }
  Write-Host "$Command"
    return $Command
}

function Invoke-Expression-And-Check{
    param (
        [string]$Command
    )
    $Command=$(Append-To-Command "$Command")
    Invoke-Expression $Command
    if ($LASTEXITCODE -gt 0) {
        exit $LASTEXITCODE
    }
}
# Check and create resource group if not exist
$Result = (az group exists --name $ResourceGroup)
if ($Result -eq "false") {
    Write-Host "Creating resource group...$ResourceGroup"
    $Command="az group create --name $ResourceGroup -l $Location"
    Invoke-Expression-And-Check "$Command"
}
# Create service plan
$ServicePlanName = $Name + "_service_plan"
Write-Host "Creating service plan...$ServicePlanName"
$Command="az appservice plan create --name $ServicePlanName --sku $Sku --location $location --is-linux -g $ResourceGroup"
Invoke-Expression-And-Check "$Command"
# Create app
Write-Host "Creating app...$Name"
$Command="az webapp create --name $Name -p $ServicePlanName --deployment-container-image-name $ImageTag --startup-file 'bash start.sh' -g $ResourceGroup"
Invoke-Expression-And-Check "$Command"
# Config environment variable
Write-Host "Config app...$Name"
$Command="az webapp config appsettings set -g $ResourceGroup --name $Name --settings USER_AGENT=promptflow-appservice ('@settings.json')"
Invoke-Expression-And-Check "$Command"
Write-Host "Please go to https://ms.portal.azure.com/ to config environment variables and restart the app: $Name at (Settings>Configuration) or (Settings>Environment variables)"
Write-Host "Reach deployment logs at (Deployment>Deployment Central) and app logs at (Monitoring>Log stream)"
Write-Host "Reach advanced deployment tools at https://$Name.scm.azurewebsites.net/"
Write-Host "Reach more details about app service at https://learn.microsoft.com/en-us/azure/app-service/"
