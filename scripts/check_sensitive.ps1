$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $RepoRoot
try {
    $Patterns = @(
        'sk-[A-Za-z0-9_-]{20,}',
        '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----',
        'C:\\Users\\[A-Za-z0-9._-]+',
        '\x{6731}\x{6b27}\x{7fd4}',
        '\x{6708}\x{4e4b}\x{6697}\x{9762}\x{9762}\x{8bd5}\x{4eba}\x{624d}\x{8d44}\x{6599}'
    )
    $Hits = @()
    foreach ($Pattern in $Patterns) {
        $Result = & rg --hidden --line-number --glob '!.git/**' --glob '!.venv/**' --glob '!build/**' --glob '!dist/**' --glob '!.pytest-tmp/**' --glob '!scripts/check_sensitive.ps1' --regexp $Pattern .
        if ($LASTEXITCODE -eq 0) { $Hits += $Result }
        elseif ($LASTEXITCODE -ne 1) { throw "rg failed while scanning the repository" }
    }
    if ($Hits.Count -gt 0) {
        $Hits | Write-Error
        exit 1
    }
    Write-Host "Sensitive-data scan passed."
}
finally {
    Pop-Location
}
