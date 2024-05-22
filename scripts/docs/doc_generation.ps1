<#
.DESCRIPTION
Script to build doc site

.EXAMPLE
PS> ./doc_generation.ps1 -SkipInstall # skip pip install
PS> ./doc_generation.ps1 -BuildLinkCheck -WarningAsError:$true -SkipInstall

#>
[CmdletBinding()]
param(
    [switch]$SkipInstall,
    [switch]$WarningAsError = $false,
    [switch]$BuildLinkCheck = $false,
    [switch]$WithReferenceDoc = $false
)

[string] $ScriptPath = $PSCommandPath | Split-Path -Parent
[string] $RepoRootPath = $ScriptPath | Split-Path -Parent | Split-Path -Parent
[string] $DocPath = [System.IO.Path]::Combine($RepoRootPath, "docs")
[string] $TempDocPath = New-TemporaryFile | % { Remove-Item $_; New-Item -ItemType Directory -Path $_ }
[string] $PkgSrcPath = [System.IO.Path]::Combine($RepoRootPath, "src")
[string] $OutPath = [System.IO.Path]::Combine($ScriptPath, "_build")
[string] $SphinxApiDoc = [System.IO.Path]::Combine($DocPath, "sphinx_apidoc.log")
[string] $SphinxBuildDoc = [System.IO.Path]::Combine($DocPath, "sphinx_build.log")
[string] $WarningErrorPattern = "WARNING:|ERROR:|CRITICAL:| broken "
[System.Collections.ArrayList]$IncludeList = @("promptflow-tracing", "promptflow-core", "promptflow-devkit", "promptflow-azure", "promptflow-rag", "promptflow-evals")
$apidocWarningsAndErrors = $null
$buildWarningsAndErrors = $null

if (-not $SkipInstall){
    # Prepare doc generation packages
    pip install pydata-sphinx-theme==0.11.0
    pip install sphinx==5.1
    pip install sphinx-copybutton==0.5.0
    pip install sphinx_design==0.3.0
    pip install sphinx-sitemap==2.2.0
    pip install sphinx-togglebutton==0.3.2
    pip install sphinxext-rediraffe==0.2.7
    pip install sphinxcontrib-mermaid==0.8.1
    pip install ipython-genutils==0.2.0
    pip install myst-nb==0.17.1
    pip install numpydoc==1.5.0
    pip install myst-parser==0.18.1
    pip install matplotlib==3.4.3
    pip install jinja2==3.0.1
    pip install jupyter-sphinx==0.4.0
    Write-Host "===============Finished install requirements==============="
}


function ProcessFiles {
    # Exclude files not mean to be in doc site
    $exclude_files = "README.md", "dev"
    foreach ($f in $exclude_files)
    {
        $full_path = [System.IO.Path]::Combine($TempDocPath, $f)
        Remove-Item -Path $full_path -Recurse
    }
}

Write-Host "===============PreProcess Files==============="
Write-Host "Copy doc to: $TempDocPath"
ROBOCOPY $DocPath $TempDocPath /S /NFL /NDL /XD "*.git" [System.IO.Path]::Combine($DocPath, "_scripts\_build")
ProcessFiles

function Update-Sub-Pkg-Index-Title {
    param (
        [string] $SubPkgRefDocPath,
        [string] $SubPkgName
    )
    # This is used to update the title of the promptflow.rst file in the sub package
    # from 'promptflow namespaces' to package name
    $IndexRst = [System.IO.Path]::Combine($SubPkgRefDocPath, "promptflow.rst")
    $IndexContent = Get-Content $IndexRst
    $IndexContent[0] = ("{0} package" -f $SubPkgName)
    $IndexContent[1] = "================================="
    $IndexContent[2] = ".. py:module:: promptflow"
    $IndexContent[3] = "   :noindex:"
    Set-Content $IndexRst $IndexContent
}

function Add-Changelog {
    $ChangelogFolder = [System.IO.Path]::Combine($TempDocPath, "reference\changelog")
    New-Item -ItemType Directory -Path $ChangelogFolder -Force
    Write-Host "===============Collect Package ChangeLog==============="
    $TocTreeContent = @("", "``````{toctree}", ":maxdepth: 1", ":hidden:", "")
    foreach($Item in Get-Childitem -path $PkgSrcPath)
    {
        if((-not ($IncludeList -contains $Item.Name)) -and ($Item.Name -ne "promptflow")){
            continue
        }
        # Collect CHANGELOG, name with package.md
        $ChangelogPath = [System.IO.Path]::Combine($Item.FullName, "CHANGELOG.md")
        $TargetChangelogPath = [System.IO.Path]::Combine($ChangelogFolder, "{0}.md" -f $Item.Name)
        if($Item.Name -ne "promptflow"){
            $TocTreeContent += $Item.name
        }
        Copy-Item -Path $ChangelogPath -Destination $TargetChangelogPath
    }
    $TocTreeContent += "``````"
    # Add subpackage index to promptflow changelog
    $PromptflowChangelog = [System.IO.Path]::Combine($ChangelogFolder, "promptflow.md")
    $PromptflowChangelogContent = Get-Content $PromptflowChangelog
    $PromptflowChangelogContent[0] = "# promptflow package"
    $PromptflowChangelogContent += $TocTreeContent
    Set-Content $PromptflowChangelog $PromptflowChangelogContent
}

function Add-Api-Reference {
    $RefDocRelativePath = "reference\python-library-reference"
    $RefDocPath = [System.IO.Path]::Combine($TempDocPath, $RefDocRelativePath)
    $PlaceHolderFile = [System.IO.Path]::Combine($RefDocPath, "promptflow.md")
    if(!(Test-Path $RefDocPath)){
        throw "Reference doc path not found. Please make sure '$RefDocRelativePath' is under '$DocPath'"
    }
    Remove-Item $PlaceHolderFile -Force
    $ApidocWarningsAndErrors = [System.Collections.ArrayList]::new()
    foreach($Item in Get-Childitem -path $PkgSrcPath){
        if(-not ($IncludeList -contains $Item.Name)){
            continue
        }
        # Build API reference doc
        $SubPkgPath = [System.IO.Path]::Combine($Item.FullName, "promptflow")
        $SubPkgRefDocPath = [System.IO.Path]::Combine($RefDocPath, $Item.Name)
        Write-Host "===============Build $Item Reference Doc==============="
        $TemplatePath = [System.IO.Path]::Combine($RepoRootPath, "scripts\docs\api_doc_templates")
        sphinx-apidoc --separate --module-first --no-toc --implicit-namespaces "$SubPkgPath" -o "$SubPkgRefDocPath" -t $TemplatePath | Tee-Object -FilePath $SphinxApiDoc
        $SubPkgWarningsAndErrors = Select-String -Path $SphinxApiDoc -Pattern $WarningErrorPattern
        if($SubPkgWarningsAndErrors){
            $ApidocWarningsAndErrors.AddRange($SubPkgWarningsAndErrors)
        }
        Update-Sub-Pkg-Index-Title $SubPkgRefDocPath $Item.Name
    }
}

function Add-Metadata{
    param (
        [string] $NotebookPath,
        [string] $NotebookRepoPath,
        [System.Collections.ArrayList] $AuthorList
    )
    if (-not $AuthorList){
        # Skip insert if author list not set
        throw "Skip Add Metadata: $NotebookPath - Author list not set"
        return
    }
    $NotebookContent = Get-Content $NotebookPath -Raw | ConvertFrom-Json
    # Covert to System.Collections.ArrayList to avoid 'Collection was of a fixed size' error.
    $NotebookContent.cells = [System.Collections.ArrayList]::new($NotebookContent.cells)
    if($NotebookContent.cells[0].source.Length -gt 1){
        # If the first cell length > 1, indicate there are more things than title it self in the first cell
        throw "Skip Add Metadata: $NotebookPath - First cell length > 1, only leave title to that cell."
        return
    }
    $MetadataFormat = "Authored by:&nbsp;{0}{1}"
    $SingleAuthor = "&nbsp;<a href='https://github.com/{0}' target='_blank'><img src='https://github.com/{0}.png' alt='Avatar' class='avatar dark-light'></a>"
    $JumpLink = "<a href='{0}' target='_blank'><img decoding='async' loading='lazy' src='https://img.shields.io/badge/Open%20on%20GitHub-grey?logo=github' alt='Open on GitHub' class='img_ev3q' style='float: right;'></a>" -f $NotebookRepoPath
    $Authors = $AuthorList | ForEach-Object { $SingleAuthor -f $_.replace("@github.com", "") }
    $Metadata = $MetadataFormat -f ($Authors -join ""), $JumpLink
    # Insert metadata to cells
    $MetadataCell = @{
        "cell_type" = "markdown";
        "metadata" = @{};
        "source" = @($Metadata)
    }
    $NotebookContent.cells.Insert(1, $MetadataCell)
    $NotebookContent | ConvertTo-Json -Depth 100 | Set-Content $NotebookPath
}

function Add-Notebook
{
    Write-Host "===============Collect Package Notebooks==============="
    $NotebookRootPath = [System.IO.Path]::Combine($RepoRootPath, "examples")
    $TargetNotebookPath = [System.IO.Path]::Combine($TempDocPath, "tutorials")
    # Create section list
    $SectionNames = "Tracing", "Prompty", "Flow", "Rag"
    $Sections = [ordered]@{
        Tracing=[System.Collections.ArrayList]::new();
        Prompty=[System.Collections.ArrayList]::new();
        Flow=[System.Collections.ArrayList]::new()
        Rag=[System.Collections.ArrayList]::new()
    }
    foreach($Item in Get-Childitem -path $NotebookRootPath -Recurse -Filter "*.ipynb")
    {
        # Notebook to build must have metadata: {"build_doc": {"category": "local/azure"}}
        $NotebookContent = Get-Content $Item.FullName -Raw | ConvertFrom-Json
        if(-not $NotebookContent.metadata.build_doc){
            continue
        }
        $RepoPath = $Item.FullName.Replace($RepoRootPath, "https://github.com/microsoft/promptflow/tree/main/")
        $SectionName = $NotebookContent.metadata.build_doc.section
        [int]$Weight = $NotebookContent.metadata.build_doc.weight
        $Category = $NotebookContent.metadata.build_doc.category
        $AuthorList = $NotebookContent.metadata.build_doc.author
        # If category is 'azure', add 1000 to weight
        if($Category -eq "azure"){
            $Weight += 1000
        }
        # Add ItemName, Category tuple to sections
        $Sections[$SectionName].Add([Tuple]::Create($Item.Name.Replace(".ipynb", ""), $Weight))
        # Copy notebook to doc path
        Write-Host "Adding Notebook $Item ..."
        $MediaDir = $Item.FullName + '\..\media'
        Copy-Item -Path $Item.FullName -Destination $TargetNotebookPath
        if(Test-Path $MediaDir){
            # copy image referenced in notebook
            Write-Host "Copying media files from $MediaDir ..."
            Copy-Item -Path $MediaDir -Destination $TargetNotebookPath -Recurse -Force
        }
        # Append metadata to notebook
        $CopiedNotebookPath = [System.IO.Path]::Combine($TargetNotebookPath, $Item.Name)
        Add-Metadata $CopiedNotebookPath $RepoPath $AuthorList
    }
    # Reverse sort each section list by Weight
    foreach($SectionName in $SectionNames){
        $Sections[$SectionName] = $Sections[$SectionName] | Sort-Object -Property { $_.Item2 }
    }
    $TocTreeContent = @("", "``````{{toctree}}", ":caption: {0}", ":hidden:", ":maxdepth: 1", "", "{1}", "``````")
    # Build toctree content for each section, append to tutorials index.md
    $TutorialIndex = [System.IO.Path]::Combine($TargetNotebookPath, "index.md")
    foreach($SectionName in $SectionNames){
        $SectionTocTree = $TocTreeContent -join "`n"
        # Join Item1 to a string in list
        $ExampleList = ($Sections[$SectionName] | ForEach-Object { $_.Item1 }) -join "`n"
        $SectionTocTree = $SectionTocTree -f $SectionName, $ExampleList
        Write-Debug $SectionTocTree
        Add-Content -Path $TutorialIndex -Value $SectionTocTree
    }
}

if($WithReferenceDoc){
    Add-Api-Reference
}
# Build subpackage changelog
Add-Changelog
# Build notebook examples
Add-Notebook

Write-Host "===============Build Documentation with internal=${Internal}==============="
$BuildParams = [System.Collections.ArrayList]::new()
if($WarningAsError){
    $BuildParams.Add("-W")
    $BuildParams.Add("--keep-going")
}
if($BuildLinkCheck){
    $BuildParams.Add("-blinkcheck")
}
sphinx-build $TempDocPath $OutPath -c $ScriptPath $BuildParams -v | Tee-Object -FilePath $SphinxBuildDoc
$buildWarningsAndErrors = Select-String -Path $SphinxBuildDoc -Pattern $WarningErrorPattern

Write-Host "Clean path: $TempDocPath"
Remove-Item $TempDocPath -Recurse -Confirm:$False -Force


if ($buildWarningsAndErrors) {
    Write-Host "=============== Build warnings and errors ==============="
    foreach ($line in $buildWarningsAndErrors) {
        Write-Host $line -ForegroundColor Red
    }
}