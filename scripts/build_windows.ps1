param(
    [string]$Python = "python",
    [ValidateSet("Unsigned", "Signed")]
    [string]$SigningMode = "Unsigned",
    [string]$SignTool = "",
    [string]$CertificateThumbprint = "",
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
$Utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $Utf8
$OutputEncoding = $Utf8
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
. (Join-Path $PSScriptRoot "signing.ps1")
Push-Location $RepoRoot
try {
    & $Python -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name YidaAI `
        --version-file installer/version_info.txt `
        --paths src `
        --hidden-import pypdf `
        src/yida_ai/__main__.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

    $SmokeData = Join-Path $RepoRoot "build\YidaAI-smoke-data"
    $Executable = Join-Path $RepoRoot "dist\YidaAI\YidaAI.exe"
    $Arguments = @(
        "--headless-demo",
        "--mock", ('"' + (Join-Path $RepoRoot "examples\captions\demo.jsonl") + '"'),
        "--data-dir", ('"' + $SmokeData + '"')
    )
    $Process = Start-Process -FilePath $Executable -ArgumentList $Arguments -Wait -PassThru -WindowStyle Hidden
    if ($Process.ExitCode -ne 0) { throw "Packaged smoke test failed with exit code $($Process.ExitCode)" }
    if (Test-Path -LiteralPath $SmokeData) {
        Remove-Item -LiteralPath $SmokeData -Recurse -Force
    }
    $Signed = $SigningMode -eq "Signed"
    $Verified = $false
    if ($Signed) {
        $ResolvedSignTool = Resolve-YidaSignTool -SignTool $SignTool
        Invoke-YidaSignFile `
            -Path $Executable `
            -SignTool $ResolvedSignTool `
            -CertificateThumbprint $CertificateThumbprint `
            -TimestampUrl $TimestampUrl
        $Verified = $true
    } else {
        Write-Host ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(
            "5b2T5YmN5a6J6KOF5YyF5pyq6L+b6KGM5Y+v5L+h5Luj56CB562+5ZCN44CC"
        )))
    }
    $SignatureRecord = Get-YidaSignatureRecord `
        -Path $Executable `
        -Signed $Signed `
        -SignToolVerified $Verified
    Write-YidaSignatureReport `
        -Records @($SignatureRecord) `
        -Destination (Join-Path $RepoRoot "dist\verification\executable-signature.json")
    Write-Host "Windows build and packaged smoke test passed: $Executable"
}
finally {
    Pop-Location
}
