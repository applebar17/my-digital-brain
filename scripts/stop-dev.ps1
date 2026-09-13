param(
    [ValidateSet("local", "docker")]
    [string]$Mode = "local"
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repositoryRoot

if ($Mode -eq "docker") {
    docker compose down
    exit 0
}

$processRecordPath = Join-Path $repositoryRoot "local\dev-processes.json"
if (Test-Path -LiteralPath $processRecordPath) {
    $processRecords = Get-Content -LiteralPath $processRecordPath -Raw | ConvertFrom-Json
    foreach ($record in @($processRecords)) {
        $process = Get-Process -Id ([int]$record.pid) -ErrorAction SilentlyContinue
        if ($process) {
            Stop-Process -Id $process.Id -Force
            Write-Host "Stopped $($record.name) (PID $($record.pid))."
        }
    }
    Remove-Item -LiteralPath $processRecordPath -Force
}

Write-Host "Local application processes stopped. Neo4j data and Chroma were preserved."
