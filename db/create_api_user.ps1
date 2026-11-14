<#
Create (or update) the API's runtime login that joins api_writer (migration 023; FastAPI plan P1).
Run from the project root, after migration 023:

    powershell -NoProfile -ExecutionPolicy Bypass -File db\create_api_user.ps1

If .env has no PG_API_USER / PG_API_PASSWORD yet, the script adds them (user ports_api, a random 24-character
alphanumeric password) — .env stays git-ignored. The login joins api_writer only (per-table grants in schema api,
nothing elsewhere) and gets search_path = api itself (role settings of api_writer are not inherited by its members).
The values reach psql inside the container as environment variables passed by name; they never appear on a command
line or in the output. Then:
    uv run python db/check_api_user.py      (checks the login from the host)
#>
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$envPath = Join-Path $root ".env"
$cfg = @{}
Get-Content $envPath | Where-Object { $_ -match '^\s*[A-Z_]+=' } | ForEach-Object { $k, $v = $_ -split '=', 2; $cfg[$k.Trim()] = $v.Trim() }
if (-not $cfg.PG_API_USER -or -not $cfg.PG_API_PASSWORD) {
    $pwd = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
    Add-Content -Path $envPath -Value "`r`n# The API's runtime login, member of api_writer (migration 023)`r`nPG_API_USER=ports_api`r`nPG_API_PASSWORD=$pwd" -Encoding ascii
    $cfg.PG_API_USER = "ports_api"; $cfg.PG_API_PASSWORD = $pwd
    Write-Output "added PG_API_USER / PG_API_PASSWORD to .env"
}
$sql = @'
SELECT CASE WHEN EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'u')
            THEN format('ALTER ROLE %I LOGIN PASSWORD %L', :'u', :'p')
            ELSE format('CREATE ROLE %I LOGIN PASSWORD %L', :'u', :'p') END \gexec
SELECT format('GRANT api_writer TO %I', :'u') \gexec
SELECT format('ALTER ROLE %I SET search_path = api', :'u') \gexec
SELECT rolname, rolcanlogin, (SELECT string_agg(b.rolname, ',') FROM pg_auth_members m JOIN pg_roles b ON b.oid = m.roleid
       WHERE m.member = r.oid) AS member_of FROM pg_roles r WHERE rolname = :'u';
'@
$tmp = Join-Path $env:TEMP "api_user.sql"
[IO.File]::WriteAllText($tmp, $sql, (New-Object Text.UTF8Encoding $false))
$env:API_USER = $cfg.PG_API_USER; $env:API_PWD = $cfg.PG_API_PASSWORD
try {
    docker cp $tmp ports-postgres:/tmp/api_user.sql | Out-Null
    docker exec -e API_USER -e API_PWD ports-postgres sh -c 'psql -U postgres -d ports_logistics -X -q -v ON_ERROR_STOP=1 -v u=$API_USER -v p=$API_PWD -f /tmp/api_user.sql; rm -f /tmp/api_user.sql'
    if ($LASTEXITCODE -ne 0) { throw "psql failed" }
} finally {
    foreach ($n in "API_USER", "API_PWD") { [Environment]::SetEnvironmentVariable($n, $null, "Process") }
    [IO.File]::Delete($tmp)
}
