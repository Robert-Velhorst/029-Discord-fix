[CmdletBinding(SupportsShouldProcess = $true, DefaultParameterSetName = 'Prepare')]
param(
    [Parameter(Mandatory = $true, ParameterSetName = 'Prepare')]
    [ValidatePattern('^[a-p]{32}$')]
    [string[]]$ExtensionId,
    [Parameter(ParameterSetName = 'Prepare')]
    [switch]$Register,
    [Parameter(Mandatory = $true, ParameterSetName = 'Remove')]
    [switch]$Unregister,
    [ValidateSet('Chrome', 'Edge', 'Both')]
    [string]$Browser = 'Both',
    [string]$HostExecutable,
    [string]$InstallDirectory,
    [string]$DataDirectory
)
$ErrorActionPreference = 'Stop'
$hostName = 'com.discordfix.companion'
if (-not $InstallDirectory) { $InstallDirectory = Join-Path $env:LOCALAPPDATA 'Programs\DiscordFix' }
if (-not $DataDirectory) { $DataDirectory = Join-Path $env:LOCALAPPDATA 'DiscordFix' }
$InstallDirectory = [System.IO.Path]::GetFullPath($InstallDirectory)
$DataDirectory = [System.IO.Path]::GetFullPath($DataDirectory)
$manifestPath = Join-Path $InstallDirectory "$hostName.json"
$registryPaths = @()
if ($Browser -in @('Chrome', 'Both')) { $registryPaths += "Software\Google\Chrome\NativeMessagingHosts\$hostName" }
if ($Browser -in @('Edge', 'Both')) { $registryPaths += "Software\Microsoft\Edge\NativeMessagingHosts\$hostName" }

# Never replace or remove a registration pointing to another installation.
if ($Register -or $Unregister) {
    foreach ($registryPath in $registryPaths) {
        $registryKey = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($registryPath)
        if ($registryKey) {
            try {
                if ($registryKey.GetValue('') -ne $manifestPath) { throw 'Another pairing registration exists. Review that installation first.' }
            } finally { $registryKey.Dispose() }
        }
    }
}
if ($Unregister) {
    $removedCount = 0
    foreach ($registryPath in $registryPaths) {
        if ($PSCmdlet.ShouldProcess("HKCU\$registryPath", 'Remove this pairing registration')) {
            [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKey($registryPath, $false)
            $removedCount++
        }
    }
    Write-Output "Completed $removedCount unregister operations. App files and data were preserved."
    return
}
if ($ExtensionId.Count -lt 1 -or $ExtensionId.Count -gt 10) { throw 'Specify between one and ten exact extension IDs.' }
if (-not $HostExecutable) { $HostExecutable = Join-Path $PSScriptRoot 'dist\DiscordFixPairing.exe' }
$HostExecutable = (Resolve-Path -LiteralPath $HostExecutable -ErrorAction Stop).ProviderPath
if (-not (Test-Path -LiteralPath $HostExecutable -PathType Leaf)) { throw 'Build DiscordFixPairing.exe first.' }
$targetHost = Join-Path $InstallDirectory 'DiscordFixPairing.exe'
$allowedOrigins = @($ExtensionId | Select-Object -Unique | ForEach-Object { "chrome-extension://$_/" })
$manifest = [ordered]@{ name = $hostName; description = 'Discord Fix local session pairing'; path = $targetHost; type = 'stdio'; allowed_origins = $allowedOrigins }
$config = @{ data_directory = $DataDirectory }
$prepared = $false
if ($PSCmdlet.ShouldProcess($InstallDirectory, 'Prepare the native pairing helper and exact origin allowlist')) {
    New-Item -ItemType Directory -Path $InstallDirectory -Force | Out-Null
    foreach ($ownedFile in @($targetHost, $manifestPath, (Join-Path $InstallDirectory 'discord-fix-pairing.json'))) {
        if (Test-Path -LiteralPath $ownedFile -PathType Leaf) {
            Copy-Item -LiteralPath $ownedFile -Destination ($ownedFile + '.previous.' + [guid]::NewGuid().ToString('N'))
        }
    }
    if ($HostExecutable -ne $targetHost) { Copy-Item -LiteralPath $HostExecutable -Destination $targetHost -Force }
    $manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding utf8
    $config | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $InstallDirectory 'discord-fix-pairing.json') -Encoding utf8
    $prepared = $true
}
if ($Register) {
    $registeredCount = 0
    foreach ($registryPath in $registryPaths) {
        if ($PSCmdlet.ShouldProcess("HKCU\$registryPath", 'Register the native pairing helper for the listed extension IDs')) {
            if (-not $prepared) { throw 'No helper was prepared. No registration will be changed.' }
            $registryKey = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($registryPath)
            try { $registryKey.SetValue('', $manifestPath, [Microsoft.Win32.RegistryValueKind]::String) }
            finally { $registryKey.Dispose() }
            $registeredCount++
        }
    }
    Write-Output "Completed $registeredCount registration operations for the current Windows user and specified extension IDs."
} else {
    if ($prepared) {
        Write-Output "Prepared $manifestPath. No browser registry entry was changed. Review it, then run this command with -Register to enable pairing."
    } else { Write-Output 'No files or browser registrations were changed.' }
}
