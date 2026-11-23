# Owner-run (Frontend plan §10.4, the done-when's local-stack E2E): the web's Playwright stack suite against the real
# API in test mode (`Serve.py --fake-roles`, no model quota) over the isolated full-data clone `portpilot-api-full`
# (127.0.0.1:55432 / portpilot_api_test), never ports-postgres. The clone must exist (made by
# `dev/tests/run_api_full_clone.ps1`); this script only starts it if stopped and reads its password.
# - The suite creates eight test identities on the clone and removes them, with all they made, at the end
#   (`dev/checks/api/Web_stack_fixture.py`); MongoDB / Qdrant are only read; uploads stay in API memory.
# - Ports: API 8011, web 3101 (apart from the real API on 8000 and the web container on 3000).
#   powershell -NoProfile -File .\dev\tests\run_web_stack.ps1
$ErrorActionPreference = 'Continue'
$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$name = 'portpilot-api-full'
$keys = 'PORTPILOT_API_TEST_DSN', 'PORTPILOT_FULL_STACK_ISOLATED', 'PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER', 'PGPASSWORD', 'PYTHONIOENCODING'
$saved = @{}
foreach ($k in $keys) { $saved[$k] = [Environment]::GetEnvironmentVariable($k, 'Process') }
$resultCode = 1
Push-Location -LiteralPath $projectRoot
try {
    $containers = @(docker container ls --all --format '{{.Names}}')
    if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop must be running.' }
    if ($containers -notcontains $name) { throw "$name is not there: make it first with .\dev\tests\run_api_full_clone.ps1" }
    $password = ((docker inspect $name --format '{{range .Config.Env}}{{println .}}{{end}}') | Where-Object { $_ -like 'POSTGRES_PASSWORD=*' }) -replace '^POSTGRES_PASSWORD=', ''
    if (-not $password) { throw "$name has no POSTGRES_PASSWORD: it was not made by run_api_full_clone.ps1." }
    docker start $name | Out-Null
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        docker exec $name pg_isready -U postgres -d portpilot_api_test *> $null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw "$name did not become ready." }
    $env:PORTPILOT_API_TEST_DSN = "host=127.0.0.1 port=55432 dbname=portpilot_api_test user=postgres password=$password"
    $env:PORTPILOT_FULL_STACK_ISOLATED = '1'
    $env:PGHOST = '127.0.0.1'; $env:PGPORT = '55432'; $env:PGDATABASE = 'portpilot_api_test'
    $env:PGUSER = 'postgres'; $env:PGPASSWORD = $password
    $env:PYTHONIOENCODING = 'utf-8'
    Push-Location -LiteralPath (Join-Path $projectRoot 'web')
    try {
        npx playwright test -c playwright.stack.config.ts
        $resultCode = $LASTEXITCODE
    } finally { Pop-Location }
} catch {
    Write-Host "FAILED: $($_.Exception.Message)"
} finally {
    foreach ($k in $keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k], 'Process') }
    Pop-Location
}
exit $resultCode
