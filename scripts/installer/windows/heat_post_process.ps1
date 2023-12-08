# Add the script to delete the pfs.bat component from the generated wxs file, which is conflicting with the pfs.bat
# component in the project.wxs.
$content = Get-Content -Path "out\promptflow.wxs"
$searchText = "pfs.bat"

for ($i = 0; $i -lt $content.Count; $i++) {
    if ($content[$i] -match $searchText) {
        $start = [Math]::Max(0, $i - 1)
        $end = [Math]::Min($i + 1, $content.Count - 1)

        $content = $content[0..($start - 1)] + $content[($end + 1)..($content.Count - 1)]
    }
}

$content | Set-Content -Path "out\promptflow.wxs"