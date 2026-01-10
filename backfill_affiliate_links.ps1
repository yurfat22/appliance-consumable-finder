param(
  [string]$DatabaseUrl,
  [string]$AssociateTag,
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$envFile = Join-Path $repoRoot "backend\.env"

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

if (-not $DatabaseUrl) {
  Write-Error "DATABASE_URL is required. Set it in backend/.env or pass -DatabaseUrl."
}

$env:AMAZON_ASSOCIATE_TAG = $AssociateTag

@"
from psycopg import connect
import os

dsn = r'''$DatabaseUrl'''
tag = os.environ.get("AMAZON_ASSOCIATE_TAG", "be3857-20")

with connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE consumables ADD COLUMN IF NOT EXISTS asin TEXT;")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_consumables_asin ON consumables (asin);")
        cur.execute(
            "UPDATE consumables "
            "SET purchase_url = 'https://www.amazon.com/dp/' || asin || '?tag=' || %s "
            "WHERE asin IS NOT NULL AND asin <> '' AND (purchase_url IS NULL OR purchase_url = '');",
            (tag,),
        )
    conn.commit()

print("Applied asin migration and backfilled purchase_url.")
"@ | & $Python -

exit $LASTEXITCODE
