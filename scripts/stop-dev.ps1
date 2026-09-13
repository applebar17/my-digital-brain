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
    $allProcesses = @(Get-CimInstance Win32_Process)
    foreach ($record in @($processRecords)) {
        $rootPid = [int]$record.pid
        $pending = [System.Collections.Generic.Queue[int]]::new()
        $processIds = [System.Collections.Generic.HashSet[int]]::new()
        $pending.Enqueue($rootPid)
        $processIds.Add($rootPid) | Out-Null
        while ($pending.Count -gt 0) {
            $parentPid = $pending.Dequeue()
            foreach ($child in @($allProcesses | Where-Object { [int]$_.ParentProcessId -eq $parentPid })) {
                $childPid = [int]$child.ProcessId
                if ($processIds.Add($childPid)) {
                    $pending.Enqueue($childPid)
                }
            }
        }
        foreach ($processId in @($processIds | Sort-Object -Descending)) {
            $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
            if ($process) {
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
                Write-Host "Stopped $($record.name) (PID $($process.Id))."
            }
        }
    }
    Remove-Item -LiteralPath $processRecordPath -Force
}

Write-Host "Local application processes stopped. Neo4j data and Chroma were preserved."
