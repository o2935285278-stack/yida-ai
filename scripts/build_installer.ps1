param(
    [Parameter(Mandatory = $true)]
    [string]$LctExecutable,
    [string]$Python = "python",
    [string]$InnoCompiler = "",
    [switch]$QaBuild,
    [ValidateSet("Unsigned", "Signed")]
    [string]$SigningMode = "Unsigned",
    [string]$SignTool = "",
    [string]$CertificateThumbprint = "",
    [string]$TimestampUrl = "http://timestamp.digicert.com",
    [switch]$FormalRelease
)

$ErrorActionPreference = "Stop"
$Utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $Utf8
$OutputEncoding = $Utf8
$ExpectedLctVersion = "1.7.1300.1822"
$ExpectedLctSha256 = "62A5C9AC04FA48EC89A28168BB5835745DD332497CA1EF6184498E6565B4CB31"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ResolvedLct = (Resolve-Path -LiteralPath $LctExecutable -ErrorAction Stop).Path
. (Join-Path $PSScriptRoot "signing.ps1")

if ($FormalRelease -and $SigningMode -ne "Signed") {
    throw "A formal Release requires Signed mode and successful SignTool verification."
}

if ([IO.Path]::GetFileName($ResolvedLct) -ne "LiveCaptions Translator.exe") {
    throw "Unexpected LCT filename. Expected: LiveCaptions Translator.exe"
}

$LctItem = Get-Item -LiteralPath $ResolvedLct
$ActualVersion = $LctItem.VersionInfo.FileVersion
$ActualHash = (Get-FileHash -LiteralPath $ResolvedLct -Algorithm SHA256).Hash
if ($ActualVersion -ne $ExpectedLctVersion) {
    throw "Unexpected LCT version: $ActualVersion (expected $ExpectedLctVersion)"
}
if ($ActualHash -ne $ExpectedLctSha256) {
    throw "Unexpected LCT SHA-256: $ActualHash"
}

if (-not $InnoCompiler) {
    $Candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    )
    $InnoCompiler = $Candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $InnoCompiler -or -not (Test-Path -LiteralPath $InnoCompiler)) {
    throw "Inno Setup 6 was not found. Install JRSoftware.InnoSetup or pass -InnoCompiler."
}

Push-Location $RepoRoot
try {
    $BuildArguments = @{
        Python = $Python
        SigningMode = $SigningMode
        SignTool = $SignTool
        CertificateThumbprint = $CertificateThumbprint
        TimestampUrl = $TimestampUrl
    }
    & (Join-Path $PSScriptRoot "build_windows.ps1") @BuildArguments
    if ($LASTEXITCODE -ne 0) { throw "Yida AI Windows build failed" }

    $ForbiddenNames = @(
        "setting.json",
        "translation_history.db",
        "config.json",
        "history.db"
    )
    $Forbidden = Get-ChildItem -LiteralPath (Join-Path $RepoRoot "dist\YidaAI") -Recurse -File |
        Where-Object { $_.Name -in $ForbiddenNames }
    if ($Forbidden) {
        throw "Private file found in application bundle: $($Forbidden.FullName -join ', ')"
    }

    $Staging = Join-Path $RepoRoot "dist\installer-staging"
    New-Item -ItemType Directory -Path $Staging -Force | Out-Null
    $Manifest = Join-Path $Staging "LCT_COMPONENT_MANIFEST.txt"
    @(
        "Component: LiveCaptions Translator",
        "Version: $ActualVersion",
        "SHA-256: $ActualHash",
        "Upstream: https://github.com/SakiRinn/LiveCaptions-Translator",
        "License: Apache License 2.0",
        "Redistribution: unmodified upstream executable"
    ) | Set-Content -LiteralPath $Manifest -Encoding utf8

    $InstallerScript = Join-Path $RepoRoot "installer\YidaAI.iss"
    $Arguments = @(
        "/DSourceRoot=$RepoRoot",
        "/DLctExecutable=$ResolvedLct",
        "/DLctManifest=$Manifest"
    )
    if ($QaBuild) { $Arguments += "/DQaBuild=1" }
    $Arguments += $InstallerScript
    & $InnoCompiler @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup build failed" }

    $InstallerName = if ($QaBuild) {
        "YidaAI-0.2.2-beta-win-x64-qa-setup.exe"
    } else {
        "YidaAI-0.2.2-beta-win-x64-setup.exe"
    }
    $Installer = Join-Path $RepoRoot "dist\installer\$InstallerName"
    if (-not (Test-Path -LiteralPath $Installer)) {
        throw "Installer output was not created: $Installer"
    }
    $Signed = $SigningMode -eq "Signed"
    $Verified = $false
    if ($Signed) {
        $ResolvedSignTool = Resolve-YidaSignTool -SignTool $SignTool
        Invoke-YidaSignFile `
            -Path $Installer `
            -SignTool $ResolvedSignTool `
            -CertificateThumbprint $CertificateThumbprint `
            -TimestampUrl $TimestampUrl
        $Verified = $true
    } else {
        Write-Host ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(
            "5b2T5YmN5a6J6KOF5YyF5pyq6L+b6KGM5Y+v5L+h5Luj56CB562+5ZCN44CC"
        )))
    }
    if ($FormalRelease -and -not $Verified) {
        throw "Signature verification failed; formal Release output is blocked."
    }
    $Executable = Join-Path $RepoRoot "dist\YidaAI\YidaAI.exe"
    $Records = @(
        Get-YidaSignatureRecord -Path $Executable -Signed $Signed -SignToolVerified $Verified
        Get-YidaSignatureRecord -Path $Installer -Signed $Signed -SignToolVerified $Verified
    )
    Write-YidaSignatureReport `
        -Records $Records `
        -Destination (Join-Path $RepoRoot "dist\verification\signature.json")

    # The installer is immutable after signing. SHA-256 is deliberately the final operation.
    $InstallerItem = Get-Item -LiteralPath $Installer
    $InstallerHash = (Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash
    Write-Host "Installer=$Installer"
    Write-Host "SizeBytes=$($InstallerItem.Length)"
    Write-Host "SHA256=$InstallerHash"
}
finally {
    Pop-Location
}
