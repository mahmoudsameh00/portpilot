# Owner-run only. Creates a disposable PostgreSQL container; never connects to ports-postgres.
# Leaves the test container available for inspection. Refuses occupied port/name; no automatic removal.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$containerName = 'portpilot-api-test'
$savedDsn = $env:PORTPILOT_API_TEST_DSN
$savedCache = $env:UV_CACHE_DIR
$savedEncoding = $env:PYTHONIOENCODING
$resultCode = 1
Push-Location -LiteralPath $projectRoot
try {
    $containers = @(docker container ls --all --format '{{.Names}}')
    if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop must be running.' }
    if ($containers -contains $containerName) { throw 'portpilot-api-test already exists. Inspect the previous run before removing its disposable container.' }
    if (Get-NetTCPConnection -LocalPort 55432 -State Listen -ErrorAction SilentlyContinue) { throw 'Port 55432 is occupied; no container started.' }
    $testPassword = [Guid]::NewGuid().ToString('N')
    $containerId = docker run --detach --name $containerName --publish '127.0.0.1:55432:5432' --env 'POSTGRES_DB=portpilot_api_test' --env 'POSTGRES_USER=postgres' --env "POSTGRES_PASSWORD=$testPassword" 'postgres:16.9'
    if ($LASTEXITCODE -ne 0) { throw 'Could not start the isolated test container.' }
    Write-Host "Created disposable container $containerName ($containerId)."
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        docker exec $containerName pg_isready -U postgres -d portpilot_api_test *> $null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw 'Test PostgreSQL did not become ready. Container retained for inspection.' }
    $env:PORTPILOT_API_TEST_DSN = "host=127.0.0.1 port=55432 dbname=portpilot_api_test user=postgres password=$testPassword"
    $env:UV_CACHE_DIR = Join-Path $projectRoot 'Notebooks/_scratch/review-uv-cache'
    $env:PYTHONIOENCODING = 'utf-8'
    uv run --no-sync python tools/run.py pipelines/scripts/api/Api_integration_check.py
    $resultCode = $LASTEXITCODE
} finally {
    $env:PORTPILOT_API_TEST_DSN = $savedDsn
    $env:UV_CACHE_DIR = $savedCache
    $env:PYTHONIOENCODING = $savedEncoding
    Pop-Location
}
exit $resultCode
