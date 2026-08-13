param(
    [string]$Destination = ""
)

$ErrorActionPreference = "Stop"
$ExpectedSha256 = "62A5C9AC04FA48EC89A28168BB5835745DD332497CA1EF6184498E6565B4CB31"
$ExpectedSize = 75321060
$DownloadUrl = "https://github.com/SakiRinn/LiveCaptions-Translator/releases/download/v1.7.1300.1822/LiveCaptionsTranslator-win-x64-withruntime.exe"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $Destination) {
    $Destination = Join-Path $RepoRoot "build\third-party\LiveCaptions Translator.exe"
}
$ResolvedDestination = [IO.Path]::GetFullPath($Destination)
$Parent = Split-Path -Parent $ResolvedDestination
New-Item -ItemType Directory -Path $Parent -Force | Out-Null
$Temporary = "$ResolvedDestination.download"

try {
    Invoke-WebRequest -UseBasicParsing -Uri $DownloadUrl -OutFile $Temporary
    $Item = Get-Item -LiteralPath $Temporary
    $Hash = (Get-FileHash -LiteralPath $Temporary -Algorithm SHA256).Hash
    if ($Item.Length -ne $ExpectedSize) {
        throw "Unexpected LCT asset size: $($Item.Length)"
    }
    if ($Hash -ne $ExpectedSha256) {
        throw "Unexpected LCT asset SHA-256: $Hash"
    }
    Move-Item -LiteralPath $Temporary -Destination $ResolvedDestination -Force
    Write-Host "Verified official LCT asset: $ResolvedDestination"
    Write-Host "SHA256=$Hash"
}
finally {
    if (Test-Path -LiteralPath $Temporary) {
        Remove-Item -LiteralPath $Temporary -Force
    }
}

