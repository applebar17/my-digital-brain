param(
    [ValidateSet("local", "docker")]
    [string]$Mode = "local",
    [switch]$InstallNeo4j,
    [switch]$StartChromaContainer,
    [switch]$NoFrontend,
    [switch]$NoBackend
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repositoryRoot

function Import-DotEnv {
    param([string]$FilePath)

    if (-not (Test-Path -LiteralPath $FilePath)) {
        throw "Environment file not found: $FilePath"
    }

    foreach ($rawLine in Get-Content -LiteralPath $FilePath) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            continue
        }
        $parts = $line.Split("=", 2)
        $name = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

function Test-TcpPort {
    param([int]$Port)

    return $null -ne (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Wait-HttpEndpoint {
    param(
        [string]$Uri,
        [int]$Attempts = 30
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 3 | Out-Null
            return
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "Timed out waiting for $Uri"
}

function Save-ProcessRecord {
    param(
        [string]$Name,
        [System.Diagnostics.Process]$Process
    )

    $processRecords = @()
    if (Test-Path -LiteralPath $script:processRecordPath) {
        $existing = Get-Content -LiteralPath $script:processRecordPath -Raw | ConvertFrom-Json
        if ($existing) {
            $processRecords = @($existing)
        }
    }
    $processRecords += [pscustomobject]@{ name = $Name; pid = $Process.Id }
    $processRecords | ConvertTo-Json | Set-Content -LiteralPath $script:processRecordPath -Encoding utf8
}

if ($Mode -eq "docker") {
    docker compose up --build -d
    docker compose ps
    Write-Host "Docker development stack started. Frontend: http://localhost:5173"
    exit 0
}

$localRuntimeDirectory = Join-Path $repositoryRoot "local"
$developmentLogDirectory = Join-Path $repositoryRoot "logs\dev"
$script:processRecordPath = Join-Path $localRuntimeDirectory "dev-processes.json"
New-Item -ItemType Directory -Force -Path $developmentLogDirectory | Out-Null

Import-DotEnv (Join-Path $repositoryRoot "src\my_digital_brain\.env")
$env:PYTHONPATH = Join-Path $repositoryRoot "src"
$env:RELATIONAL_BACKEND = "sqlite"
$env:SQLITE_PATH = "data/local/brain.sqlite3"
$env:CHROMA_HOST = "127.0.0.1"
$env:CHROMA_PORT = "8001"
$env:NEO4J_URI = "bolt://127.0.0.1:7687"
$env:LOG_DIR = "logs/dev"

$neo4jVersion = "5.26.0"
$neo4jHome = Join-Path $localRuntimeDirectory "neo4j-community-$neo4jVersion"
$neo4jExecutable = Join-Path $neo4jHome "bin\neo4j.bat"
$neo4jArchive = Join-Path $localRuntimeDirectory "neo4j-community-$neo4jVersion-windows.zip"

if (-not (Test-Path -LiteralPath $neo4jExecutable)) {
    if (-not $InstallNeo4j) {
        throw "Local Neo4j is missing. Re-run with -InstallNeo4j to download Neo4j Community $neo4jVersion from https://dist.neo4j.org."
    }
    if (-not (Test-Path -LiteralPath $neo4jArchive)) {
        Write-Host "Downloading Neo4j Community $neo4jVersion..."
        Invoke-WebRequest `
            -Uri "https://dist.neo4j.org/neo4j-community-$neo4jVersion-windows.zip" `
            -OutFile $neo4jArchive `
            -UseBasicParsing
    }
    Expand-Archive -LiteralPath $neo4jArchive -DestinationPath $localRuntimeDirectory -Force
}

if (-not (Test-TcpPort 7687)) {
    $initialPasswordMarker = Join-Path $neo4jHome ".my-digital-brain-initial-password-set"
    if (-not (Test-Path -LiteralPath $initialPasswordMarker)) {
        & (Join-Path $neo4jHome "bin\neo4j-admin.bat") dbms set-initial-password $env:NEO4J_PASSWORD 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            New-Item -ItemType File -Force -Path $initialPasswordMarker | Out-Null
        }
    }

    $neo4jLog = Join-Path $developmentLogDirectory "neo4j.log"
    $neo4jProcess = Start-Process `
        -FilePath $neo4jExecutable `
        -ArgumentList @("console") `
        -WorkingDirectory $neo4jHome `
        -RedirectStandardOutput $neo4jLog `
        -RedirectStandardError $neo4jLog `
        -WindowStyle Hidden `
        -PassThru
    Save-ProcessRecord -Name "neo4j" -Process $neo4jProcess
}
Wait-HttpEndpoint -Uri "http://127.0.0.1:7474"

if ($StartChromaContainer) {
    $chromaContainer = docker ps -a --filter "name=^my-digital-brain-chroma$" --format "{{.Names}}"
    $runningChromaContainer = docker ps --filter "name=^my-digital-brain-chroma$" --format "{{.Names}}"
    if ($chromaContainer -eq "my-digital-brain-chroma" -and $runningChromaContainer -ne "my-digital-brain-chroma") {
        docker start my-digital-brain-chroma | Out-Null
    }
}
Wait-HttpEndpoint -Uri "http://127.0.0.1:8001/api/v1/heartbeat"

$uvRuntimeDependencies = @(
    "--with", "alembic>=1.13.3",
    "--with", "chromadb-client==0.5.23",
    "--with", "fastapi>=0.115.0",
    "--with", "neo4j>=5.25.0",
    "--with", "openai>=1.55.0",
    "--with", "psycopg[binary]>=3.2.3",
    "--with", "pydantic>=2.9.2",
    "--with", "pydantic-settings>=2.6.0",
    "--with", "sqlalchemy>=2.0.36",
    "--with", "uvicorn[standard]>=0.32.0",
    "--with", "httpx>=0.27.2"
)

Write-Host "Running local relational and graph migrations..."
uv run --no-project @uvRuntimeDependencies -- python -m my_digital_brain.cli migrate-relational
uv run --no-project @uvRuntimeDependencies -- python -m my_digital_brain.cli migrate-graph

if (-not $NoBackend) {
    if (Test-TcpPort 8000) {
        Write-Host "Backend already listening on port 8000."
    } else {
        $backendLog = Join-Path $developmentLogDirectory "backend.log"
        $backendProcess = Start-Process `
            -FilePath "uv" `
            -ArgumentList (@("run", "--no-project") + $uvRuntimeDependencies + @("--", "uvicorn", "my_digital_brain.api.main:app", "--host", "127.0.0.1", "--port", "8000")) `
            -WorkingDirectory $repositoryRoot `
            -RedirectStandardOutput ($backendLog -replace "\.log$", ".out.log") `
            -RedirectStandardError ($backendLog -replace "\.log$", ".err.log") `
            -WindowStyle Hidden `
            -PassThru
        Save-ProcessRecord -Name "backend" -Process $backendProcess
    }
    Wait-HttpEndpoint -Uri "http://127.0.0.1:8000/health"
}

if (-not $NoFrontend) {
    if (Test-TcpPort 5173) {
        Write-Host "Frontend already listening on port 5173."
    } else {
        $frontendLog = Join-Path $developmentLogDirectory "frontend.log"
        $frontendProcess = Start-Process `
            -FilePath "npm.cmd" `
            -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1") `
            -WorkingDirectory (Join-Path $repositoryRoot "frontend") `
            -RedirectStandardOutput ($frontendLog -replace "\.log$", ".out.log") `
            -RedirectStandardError ($frontendLog -replace "\.log$", ".err.log") `
            -WindowStyle Hidden `
            -PassThru
        Save-ProcessRecord -Name "frontend" -Process $frontendProcess
    }
    Wait-HttpEndpoint -Uri "http://127.0.0.1:5173"
}

Write-Host "Local development stack started."
Write-Host "Frontend: http://127.0.0.1:5173"
Write-Host "Backend:  http://127.0.0.1:8000"
Write-Host "Logs:     $developmentLogDirectory"
