param(
    [string]$InstallDirectory = ""
)

$ErrorActionPreference = "Stop"
$Version = "6.7.3"
$ExpectedSha256 = "9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732"
$DownloadUrl = "https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe"
if (-not $InstallDirectory) {
    $BaseDirectory = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { $env:TEMP }
    $InstallDirectory = Join-Path $BaseDirectory "inno-setup-$Version"
}
$InstallDirectory = [IO.Path]::GetFullPath($InstallDirectory)
$Download = Join-Path $env:TEMP "innosetup-$Version-yida.exe"

try {
    Invoke-WebRequest -UseBasicParsing -Uri $DownloadUrl -OutFile $Download
    $Hash = (Get-FileHash -LiteralPath $Download -Algorithm SHA256).Hash
    if ($Hash -ne $ExpectedSha256) {
        throw "Unexpected Inno Setup SHA-256: $Hash"
    }
    & $Download /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- "/DIR=$InstallDirectory"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup installation failed: $LASTEXITCODE" }
    $Compiler = Join-Path $InstallDirectory "ISCC.exe"
    if (-not (Test-Path -LiteralPath $Compiler)) {
        throw "Inno Setup compiler was not installed: $Compiler"
    }
    Write-Host "INNO_COMPILER=$Compiler"
}
finally {
    if (Test-Path -LiteralPath $Download) {
        Remove-Item -LiteralPath $Download -Force
    }
}
