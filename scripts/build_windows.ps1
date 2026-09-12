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
    & $Python -c "import comtypes.client; comtypes.client.GetModule('UIAutomationCore.dll')"
    if ($LASTEXITCODE -ne 0) { throw "UI Automation binding generation failed" }
    & $Python -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name YidaAI `
        --version-file installer/version_info.txt `
        --paths src `
        --hidden-import pypdf `
        --hidden-import comtypes.gen.UIAutomationClient `
        --collect-all tkinterdnd2 `
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
        $ResolvedSmoke = [IO.Path]::GetFullPath($SmokeData)
        $BuildRoot = [IO.Path]::GetFullPath((Join-Path $RepoRoot "build")) + '\'
        if (-not $ResolvedSmoke.StartsWith($BuildRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Smoke cleanup target escaped build directory"
        }
        Remove-Item -LiteralPath $SmokeData -Recurse -Force
    }
    $LicenseDirectory = Join-Path $RepoRoot "dist\YidaAI\licenses"
    New-Item -ItemType Directory -Path $LicenseDirectory -Force | Out-Null
    $PythonLicense = & $Python -X utf8 -c "import pathlib, sys; print(pathlib.Path(sys.base_prefix, 'LICENSE.txt').resolve())"
    $PythonLicense = [IO.Path]::GetFullPath([string]$PythonLicense)
    if ($LASTEXITCODE -ne 0 -or -not $PythonLicense) {
        throw "Could not determine the Python license path for license packaging."
    }
    if (-not (Test-Path -LiteralPath $PythonLicense)) {
        throw "Python license file was not found: $PythonLicense"
    }
    Copy-Item -LiteralPath $PythonLicense -Destination (Join-Path $LicenseDirectory "CPython-LICENSE.txt") -Force
    $LicenseSources = @(
        @{ Distribution = "comtypes-*.dist-info"; File = "licenses\LICENSE.txt"; Output = "comtypes-LICENSE.txt" },
        @{ Distribution = "tkinterdnd2-*.dist-info"; File = "licenses\LICENSE"; Output = "tkinterdnd2-LICENSE.txt" },
        @{ Distribution = "pypdf-*.dist-info"; File = "licenses\LICENSE"; Output = "pypdf-LICENSE.txt" },
        @{ Distribution = "PyInstaller-*.dist-info"; File = "licenses\COPYING.txt"; Output = "PyInstaller-COPYING.txt" }
    )
    $SitePackages = & $Python -X utf8 -c "import sysconfig; print(sysconfig.get_path('purelib'))"
    $SitePackages = [IO.Path]::GetFullPath([string]$SitePackages)
    if ($LASTEXITCODE -ne 0 -or -not $SitePackages) {
        throw "Could not determine site-packages for license packaging."
    }
    if (-not (Test-Path -LiteralPath $SitePackages)) {
        throw "Could not locate site-packages for license packaging: $SitePackages"
    }
    foreach ($License in $LicenseSources) {
        $Distribution = Get-ChildItem -LiteralPath $SitePackages -Directory -Filter $License.Distribution |
            Select-Object -First 1
        if (-not $Distribution) { throw "Distribution metadata missing: $($License.Distribution)" }
        $Source = Join-Path $Distribution.FullName $License.File
        if (-not (Test-Path -LiteralPath $Source)) { throw "Dependency license missing: $Source" }
        Copy-Item -LiteralPath $Source -Destination (Join-Path $LicenseDirectory $License.Output) -Force
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
