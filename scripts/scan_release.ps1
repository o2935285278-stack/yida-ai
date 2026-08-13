param(
    [Parameter(Mandatory = $true)]
    [string[]]$Path,
    [switch]$RequireAvailable
)

$ErrorActionPreference = "Stop"
$Resolved = @($Path | ForEach-Object { (Resolve-Path -LiteralPath $_ -ErrorAction Stop).Path })
$Candidates = @()
$PlatformRoot = Join-Path $env:ProgramData "Microsoft\Windows Defender\Platform"
if (Test-Path -LiteralPath $PlatformRoot) {
    $Candidates += Get-ChildItem -LiteralPath $PlatformRoot -Directory |
        Sort-Object Name -Descending |
        ForEach-Object { Join-Path $_.FullName "MpCmdRun.exe" }
}
$Candidates += Join-Path $env:ProgramFiles "Windows Defender\MpCmdRun.exe"
$Scanner = $Candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $Scanner) {
    if ($RequireAvailable) { throw "Microsoft Defender command-line scanner is unavailable." }
    Write-Warning "Microsoft Defender scanner unavailable; no malware result is claimed."
    exit 0
}

foreach ($Target in $Resolved) {
    & $Scanner -Scan -ScanType 3 -File $Target -DisableRemediation
    if ($LASTEXITCODE -ne 0) {
        throw "Microsoft Defender scan failed or detected a threat: $Target (exit $LASTEXITCODE)"
    }
    Write-Host "Microsoft Defender scan passed: $Target"
}

