function Resolve-YidaSignTool {
    param([string]$SignTool = "")
    if ($SignTool -and (Test-Path -LiteralPath $SignTool)) {
        return (Resolve-Path -LiteralPath $SignTool).Path
    }
    $KitsRoot = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
    if (Test-Path -LiteralPath $KitsRoot) {
        $Candidate = Get-ChildItem -LiteralPath $KitsRoot -Directory |
            Sort-Object Name -Descending |
            ForEach-Object { Join-Path $_.FullName "x64\signtool.exe" } |
            Where-Object { Test-Path -LiteralPath $_ } |
            Select-Object -First 1
        if ($Candidate) { return $Candidate }
    }
    $Command = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($Command) { return $Command.Source }
    throw "SignTool was not found. Install the Windows SDK or pass -SignTool."
}

function Invoke-YidaSignFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$SignTool,
        [Parameter(Mandatory = $true)][string]$CertificateThumbprint,
        [Parameter(Mandatory = $true)][string]$TimestampUrl
    )
    if (-not (Test-Path -LiteralPath $Path)) { throw "Signing target not found: $Path" }
    if (-not $CertificateThumbprint) {
        throw "Signed mode requires -CertificateThumbprint for a certificate in the Windows certificate store."
    }
    & $SignTool sign /sha1 $CertificateThumbprint /fd SHA256 /tr $TimestampUrl /td SHA256 $Path
    if ($LASTEXITCODE -ne 0) { throw "SHA-256 signing failed: $Path" }
    & $SignTool verify /pa /all /v $Path
    if ($LASTEXITCODE -ne 0) { throw "SignTool verification failed: $Path" }
}

function Get-YidaSignatureRecord {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][bool]$Signed,
        [Parameter(Mandatory = $true)][bool]$SignToolVerified
    )
    $Record = [ordered]@{
        Path = [IO.Path]::GetFileName($Path)
        Signed = $Signed
        Signer = ""
        DigestAlgorithm = if ($Signed) { "SHA-256" } else { "none" }
        TimestampStatus = if ($Signed) { "unverified" } else { "not-applicable" }
        SignToolVerified = $SignToolVerified
    }
    if ($Signed) {
        $Signature = Get-AuthenticodeSignature -LiteralPath $Path
        $Record.Signer = if ($Signature.SignerCertificate) {
            $Signature.SignerCertificate.Subject
        } else { "" }
        $Record.TimestampStatus = if ($Signature.TimeStamperCertificate) {
            "RFC3161 timestamp present"
        } else { "missing" }
        $Record.AuthenticodeStatus = [string]$Signature.Status
    }
    return [pscustomobject]$Record
}

function Write-YidaSignatureReport {
    param(
        [Parameter(Mandatory = $true)][object[]]$Records,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    $Directory = Split-Path -Parent $Destination
    New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    [ordered]@{
        GeneratedAtUtc = [DateTime]::UtcNow.ToString("o")
        CredentialsIncluded = $false
        ThirdPartyLctResigned = $false
        Files = $Records
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $Destination -Encoding utf8
}
