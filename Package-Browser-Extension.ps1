$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$source = Join-Path $PSScriptRoot 'browser-extension'
$outputDirectory = Join-Path $PSScriptRoot 'dist'

if (-not (Test-Path -LiteralPath (Join-Path $source 'manifest.json'))) {
    throw 'Browser extension manifest is missing.'
}
$manifest = Get-Content -LiteralPath (Join-Path $source 'manifest.json') -Raw | ConvertFrom-Json
if ($manifest.version -notmatch '^\d+\.\d+\.\d+$') {
    throw 'Browser extension version must contain three numeric components.'
}
$archive = Join-Path $outputDirectory "Discord-Fix-Browser-Extension-$($manifest.version).zip"
$files = @('manifest.json', 'service-worker.js', 'sidepanel.css', 'sidepanel.html', 'sidepanel.js') |
    ForEach-Object { Join-Path $source $_ }
foreach ($file in $files) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "Browser extension file is missing: $file"
    }
}
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
Compress-Archive -LiteralPath $files -DestinationPath $archive -CompressionLevel Optimal -Force
Write-Output "Created: $archive"
