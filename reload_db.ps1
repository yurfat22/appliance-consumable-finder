param(
  [string]$Input,
  [string]$Contractor,
  [switch]$Truncate,
  [string]$DatabaseUrl,
  [string]$AssociateTag,
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

if (-not $Input -and -not $Contractor) {
  Write-Error "Provide -Input and/or -Contractor."
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$loader = Join-Path $repoRoot "backend\tools\load_supabase.py"
$envFile = Join-Path $repoRoot "backend\.env"

if (-not (Test-Path $loader)) {
  Write-Error "Loader not found at $loader"
}

$envMap = @{}
if (Test-Path $envFile) {
  foreach ($line in Get-Content $envFile) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
    $parts = $trimmed.Split("=", 2)
    if ($parts.Count -eq 2) {
      $envMap[$parts[0].Trim()] = $parts[1].Trim()
    }
  }
}

if (-not $DatabaseUrl -and $envMap.ContainsKey("DATABASE_URL")) {
  $DatabaseUrl = $envMap["DATABASE_URL"]
}

if (-not $AssociateTag) {
  if ($envMap.ContainsKey("AMAZON_ASSOCIATE_TAG")) {
    $AssociateTag = $envMap["AMAZON_ASSOCIATE_TAG"]
  } else {
    $AssociateTag = "be3857-20"
  }
}

$argsList = @()
if ($Input) {
  $argsList += "--input"
  $argsList += $Input
}
if ($Contractor) {
  $argsList += "--contractor"
  $argsList += $Contractor
}
if ($DatabaseUrl) {
  $argsList += "--database-url"
  $argsList += $DatabaseUrl
}
if ($Truncate) {
  $argsList += "--truncate"
}

$env:AMAZON_ASSOCIATE_TAG = $AssociateTag

if ($DatabaseUrl) {
  @"
from psycopg import connect

dsn = r'''$DatabaseUrl'''
with connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE consumables ADD COLUMN IF NOT EXISTS asin TEXT;")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_consumables_asin ON consumables (asin);")
    conn.commit()
print("Applied asin migration.")
"@ | & $Python -
}

& $Python $loader @argsList
exit $LASTEXITCODE
