# Owner-run only (stabilization plan: the full-data Api_check gate). Creates a NEW disposable PostgreSQL container
# `portpilot-api-full` on 127.0.0.1:55432, copies into it the logins (without the postgres superuser) and the whole
# `ports_logistics` database as `portpilot_api_test`, then runs Api_check.py against that clone only.
# - ports-postgres is only READ (pg_dumpall --roles-only, pg_dump); nothing is written to it.
# - Refuses an existing container name or a busy port 55432; leaves the clone running for inspection afterwards.
# - MongoDB and Qdrant are the normal local containers (read); models are fake (Api_check uses FakeRoles).
# Again on the same clone:  powershell -NoProfile -File .\dev\tests\run_api_full_clone.ps1 -Reuse
# Remove the clone later with:  docker rm -f portpilot-api-full
# 'Continue', not 'Stop': Windows PowerShell 5.1 turns any stderr line of a native program (docker's harmless initdb
# warning, psql notices) into a terminating error under 'Stop' (2026-11-15). Every native step checks $LASTEXITCODE
# and throws itself; the cmdlets that matter carry -ErrorAction Stop.
param([switch]$Reuse)   # -Reuse: run Api_check again on an existing clone (no new copy)
$ErrorActionPreference = 'Continue'
$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$name = 'portpilot-api-full'
$dump = Join-Path $env:TEMP 'portpilot_full_clone'
$saved = @{}
foreach ($k in 'PORTPILOT_API_TEST_DSN', 'PORTPILOT_FULL_STACK_ISOLATED', 'PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER', 'PGPASSWORD', 'PYTHONIOENCODING') {
    $saved[$k] = [Environment]::GetEnvironmentVariable($k, 'Process')
}
$resultCode = 1
Push-Location -LiteralPath $projectRoot
try {
    $containers = @(docker container ls --all --format '{{.Names}}')
    if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop must be running.' }
    if ($containers -notcontains 'ports-postgres') { throw 'ports-postgres is not there; start it first: docker start ports-postgres' }
    if ($containers -contains $name) {
        if (-not $Reuse) { throw "$name already exists. Run again with -Reuse to test it again, or remove it: docker rm -f $name" }
        $password = ((docker inspect $name --format '{{range .Config.Env}}{{println .}}{{end}}') | Where-Object { $_ -like 'POSTGRES_PASSWORD=*' }) -replace '^POSTGRES_PASSWORD=', ''
        if (-not $password) { throw "$name has no POSTGRES_PASSWORD: it was not made by this script." }
        docker start $name | Out-Null
        $ready = $false
        for ($i = 0; $i -lt 60; $i++) {
            docker exec $name pg_isready -U postgres -d portpilot_api_test *> $null
            if ($LASTEXITCODE -eq 0) { $ready = $true; break }
            Start-Sleep -Seconds 1
        }
        if (-not $ready) { throw "$name did not become ready." }
        Write-Host "Reusing $name (no new copy)."
    } else {
        if (Get-NetTCPConnection -LocalPort 55432 -State Listen -ErrorAction SilentlyContinue) { throw 'Port 55432 is busy (another test container running?). Nothing started.' }
        $image = docker inspect ports-postgres --format '{{.Image}}'          # the exact image of the application database
        $password = [Guid]::NewGuid().ToString('N')
        docker run --detach --name $name --publish '127.0.0.1:55432:5432' --env 'POSTGRES_USER=postgres' --env "POSTGRES_PASSWORD=$password" --env 'POSTGRES_DB=postgres' $image | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Could not start the clone container.' }
        Write-Host "Started $name from the image of ports-postgres."
        # The postgis image first runs a temporary server to install its extensions, then stops it and starts the real
        # one: pg_isready alone answers during that first server (a restore started then is cut, 2026-11-15). Wait for the
        # entrypoint's "init process complete" line, then for the final server.
        $ready = $false
        for ($i = 0; $i -lt 180; $i++) {
            $log = (docker logs $name 2>&1 | Out-String)
            if ($log -match 'PostgreSQL init process complete') {
                docker exec $name pg_isready -U postgres *> $null
                if ($LASTEXITCODE -eq 0) { $ready = $true; break }
            }
            Start-Sleep -Seconds 1
        }
        if (-not $ready) { throw 'The clone did not become ready (container kept for inspection).' }
        New-Item -ItemType Directory -Force -Path $dump -ErrorAction Stop | Out-Null

        # 1. logins and groups (password hashes included, so the .env runtime logins work), minus the superuser
        docker exec ports-postgres sh -c "pg_dumpall -U postgres --roles-only > /tmp/roles.sql"
        if ($LASTEXITCODE -ne 0) { throw 'pg_dumpall --roles-only failed on ports-postgres.' }
        docker cp ports-postgres:/tmp/roles.sql (Join-Path $dump 'roles.sql')
        $roles = Get-Content -LiteralPath (Join-Path $dump 'roles.sql') -ErrorAction Stop | Where-Object { $_ -notmatch '^(CREATE|ALTER) ROLE postgres\b' }
        Set-Content -LiteralPath (Join-Path $dump 'roles_clone.sql') -Value $roles -Encoding utf8 -ErrorAction Stop
        docker cp (Join-Path $dump 'roles_clone.sql') "${name}:/tmp/roles.sql"
        docker exec $name psql -U postgres -d postgres -X -q -v ON_ERROR_STOP=0 -f /tmp/roles.sql 2>&1 | Select-String -Pattern 'ERROR' | Select-Object -First 5
        Write-Host 'Logins copied (postgres excluded).'

        # 2. the whole database, restored under the test name the guard accepts
        docker exec ports-postgres sh -c "pg_dump -U postgres -d ports_logistics -Fc -f /tmp/full.dump"
        if ($LASTEXITCODE -ne 0) { throw 'pg_dump failed on ports-postgres.' }
        docker cp ports-postgres:/tmp/full.dump (Join-Path $dump 'full.dump')
        if ($LASTEXITCODE -ne 0) { throw 'Could not copy the dump out of ports-postgres.' }
        docker exec ports-postgres rm -f /tmp/full.dump /tmp/roles.sql
        docker cp (Join-Path $dump 'full.dump') "${name}:/tmp/full.dump"
        if ($LASTEXITCODE -ne 0) { throw 'Could not copy the dump into the clone.' }
        docker exec $name psql -U postgres -d postgres -X -q -c 'CREATE DATABASE portpilot_api_test'
        if ($LASTEXITCODE -ne 0) { throw 'Could not create portpilot_api_test in the clone.' }
        docker exec $name sh -c "pg_restore -U postgres -d portpilot_api_test --exit-on-error /tmp/full.dump"
        if ($LASTEXITCODE -ne 0) { throw 'pg_restore failed (clone kept for inspection).' }
        $counts = docker exec $name psql -U postgres -d portpilot_api_test -X -At -c "SELECT (SELECT count(*) FROM invoices) || ' invoices, ' || (SELECT count(*) FROM employees) || ' employees, ' || (SELECT count(*) FROM finance.kpi_weekly) || ' finance weeks'"
        Write-Host "Clone restored: $counts"
        Remove-Item -LiteralPath $dump -Recurse -Force
    }

    # 3. Api_check on the clone only (every runtime pool points at 127.0.0.1:55432/portpilot_api_test)
    $env:PORTPILOT_API_TEST_DSN = "host=127.0.0.1 port=55432 dbname=portpilot_api_test user=postgres password=$password"
    $env:PORTPILOT_FULL_STACK_ISOLATED = '1'
    $env:PGHOST = '127.0.0.1'; $env:PGPORT = '55432'; $env:PGDATABASE = 'portpilot_api_test'
    $env:PGUSER = 'postgres'; $env:PGPASSWORD = $password
    $env:PYTHONIOENCODING = 'utf-8'
    uv run python dev/tools/run.py dev/checks/api/Api_check.py
    $resultCode = $LASTEXITCODE
} finally {
    foreach ($k in $saved.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k], 'Process') }
    Pop-Location
}
exit $resultCode
