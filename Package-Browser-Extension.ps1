$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$source = Join-Path $PSScriptRoot 'browser-extension'
$outputDirectory = Join-Path $PSScriptRoot 'dist'
$archive = Join-Path $outputDirectory 'Discord-Fix-Browser-Extension-0.1.1.zip'

if (-not (Test-Path -LiteralPath (Join-Path $source 'manifest.json'))) {
    throw 'Browser extension manifest is missing.'
}
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
Compress-Archive -Path (Join-Path $source '*') -DestinationPath $archive -CompressionLevel Optimal -Force
Write-Output "Created: $archive"
