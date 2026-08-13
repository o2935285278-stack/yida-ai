param(
    [switch]$SkipHistory
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Normalize-RepoPath {
    param([string]$Path)
    return ($Path -replace '\\', '/' -replace '^\./', '')
}

function Add-SanitizedFinding {
    param(
        [System.Collections.Generic.List[object]]$Findings,
        [string]$Category,
        [string]$Scope,
        [string]$Path,
        [string]$Commit = ""
    )
    $Findings.Add([pscustomobject]@{
        Category = $Category
        Scope = $Scope
        Path = (Normalize-RepoPath $Path)
        Commit = if ($Commit) { $Commit.Substring(0, [Math]::Min(12, $Commit.Length)) } else { "" }
    })
}

Push-Location $RepoRoot
try {
    $Patterns = [ordered]@{
        "credential-token" = 'sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}'
        "private-key" = '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----'
        "jwt" = 'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'
        "authorization-value" = '[Aa][Uu][Tt][Hh][Oo][Rr][Ii][Zz][Aa][Tt][Ii][Oo][Nn]\s*[:=]\s*["'']?[Bb][Ee][Aa][Rr][Ee][Rr]\s+[A-Za-z0-9._~+/-]{16,}'
        "personal-content" = '朱欧翔|月之暗面|Kimi|面试人才资料'
        "personal-email" = '[A-Za-z0-9._%+-]+@(qq|163|126|gmail|outlook)\.com'
        "cn-mobile" = '(^|[^0-9])1[3-9][0-9]{9}([^0-9]|$)'
        "cn-id" = '(^|[^0-9])[1-9][0-9]{5}(18|19|20)[0-9]{2}(0[1-9]|1[0-2])([0-2][1-9]|3[0-1])[0-9]{3}[0-9Xx]([^0-9]|$)'
        "local-user-path" = '[A-Za-z]:\\Users\\[^\\\s]+\\'
    }
    $AllowedByCategory = @{
        "personal-email" = @("installer/languages/ChineseSimplified.isl")
    }
    $Findings = New-Object 'System.Collections.Generic.List[object]'
    $CandidatePaths = @(& git ls-files --cached --others --exclude-standard)
    if ($LASTEXITCODE -ne 0) { throw "git failed while listing candidate files" }
    foreach ($Path in $CandidatePaths) {
        $Normalized = Normalize-RepoPath $Path
        if ($Normalized -eq 'scripts/check_sensitive.ps1') { continue }
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { continue }
        $Item = Get-Item -LiteralPath $Path
        if ($Item.Length -gt 5MB) { continue }
        try {
            $Content = [IO.File]::ReadAllText($Item.FullName)
        }
        catch {
            continue
        }
        if ($Content.Contains([char]0)) { continue }
        foreach ($Entry in $Patterns.GetEnumerator()) {
            if (-not [regex]::IsMatch($Content, $Entry.Value)) { continue }
            if ($AllowedByCategory[$Entry.Key] -contains $Normalized) { continue }
            Add-SanitizedFinding $Findings $Entry.Key "working-tree" $Normalized
        }
    }

    $SensitiveNamePattern = '(?i)(^|/)(\.env($|\.)|.*\.(db|sqlite|sqlite3|log|dump|bak|backup|pfx|p12|key)$|config\.json$|setting\.json$|cookies?\.json$)'
    $IgnoredPaths = @(& git status --ignored --porcelain 2>$null | ForEach-Object {
        if ($_.Length -ge 4) { $_.Substring(3) }
    })
    $CurrentNames = @($CandidatePaths) + @($IgnoredPaths)
    foreach ($Path in $CurrentNames) {
        $Normalized = Normalize-RepoPath $Path
        if ($Normalized -eq '.env.example') { continue }
        if ($Normalized -match $SensitiveNamePattern) {
            Add-SanitizedFinding $Findings "sensitive-filename" "working-tree" $Normalized
        }
    }

    $CommitsScanned = 0
    if (-not $SkipHistory) {
        if ((& git rev-parse --is-shallow-repository) -eq 'true') {
            throw "Full-history sensitive scan requires a non-shallow checkout (fetch-depth: 0)."
        }
        $Commits = @(& git rev-list --all)
        $CommitsScanned = $Commits.Count
        foreach ($Commit in $Commits) {
            foreach ($Entry in $Patterns.GetEnumerator()) {
                $Matches = & git grep -I -l -E -- $Entry.Value $Commit 2>$null
                if ($LASTEXITCODE -gt 1) { throw "git grep failed during history scan" }
                foreach ($Match in @($Matches)) {
                    $Path = ($Match -replace '^[0-9a-f]+:', '')
                    $Normalized = Normalize-RepoPath $Path
                    if ($Normalized -eq 'scripts/check_sensitive.ps1') { continue }
                    if ($AllowedByCategory[$Entry.Key] -contains $Normalized) { continue }
                    Add-SanitizedFinding $Findings $Entry.Key "git-history" $Normalized $Commit
                }
            }
            foreach ($Path in (& git ls-tree -r --name-only $Commit)) {
                $Normalized = Normalize-RepoPath $Path
                if ($Normalized -eq '.env.example') { continue }
                if ($Normalized -match $SensitiveNamePattern) {
                    Add-SanitizedFinding $Findings "sensitive-filename" "git-history" $Normalized $Commit
                }
            }
        }

        $Metadata = @(& git log --all --format='%H%x09%an%x09%ae%x09%cn%x09%ce')
        foreach ($Line in $Metadata) {
            $Fields = $Line -split "`t", 5
            if ($Fields.Count -lt 5) { continue }
            $Commit = $Fields[0]
            $Identity = ($Fields[1..4] -join ' ')
            foreach ($Entry in $Patterns.GetEnumerator()) {
                if ($Identity -match $Entry.Value) {
                    Add-SanitizedFinding $Findings $Entry.Key "git-metadata" "(author/committer identity)" $Commit
                }
            }
        }
    }

    $Unique = @($Findings | Sort-Object Category, Scope, Path, Commit -Unique)
    if ($Unique.Count -gt 0) {
        [Console]::Error.WriteLine(
            "Sensitive-data scan failed. Match values are intentionally redacted."
        )
        foreach ($Item in $Unique) {
            $Suffix = if ($Item.Commit) { " commit=$($Item.Commit)" } else { "" }
            [Console]::Error.WriteLine(
                "category=$($Item.Category) scope=$($Item.Scope) path=$($Item.Path)$Suffix"
            )
        }
        exit 1
    }
    Write-Host "Sensitive-data scan passed: working tree plus $CommitsScanned Git commits; match values were never printed."
}
finally {
    Pop-Location
}
