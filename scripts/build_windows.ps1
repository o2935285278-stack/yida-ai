param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $RepoRoot
try {
    & $Python -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name YidaAI `
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
    Write-Host "Windows build and packaged smoke test passed: $Executable"
}
finally {
    Pop-Location
}
