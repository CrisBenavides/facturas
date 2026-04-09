# process_batch_upload.ps1 - Process multiple XML files in batch
# Usage: .\process_batch_upload.ps1 -Pattern "DTE_Recibidos_*.xml"
#   or:  .\process_batch_upload.ps1 (processes all DTE_Recibidos files)

param(
    [string]$Pattern = "DTE_Recibidos"
)

$FUNCTION_URL = "https://process-xml-to-bq-wdb4jclboq-uc.a.run.app"

Write-Host "=== BATCH XML PROCESSING ===" -ForegroundColor Yellow
Write-Host "Pattern: $Pattern" -ForegroundColor Cyan
Write-Host ""

Write-Host "Getting auth token..." -ForegroundColor Yellow
try {
    $token = & gcloud auth print-identity-token 2>$null
    if ([string]::IsNullOrEmpty($token)) {
        Write-Host "✗ Failed to get auth token. Make sure you are logged in:" -ForegroundColor Red
        Write-Host "  gcloud auth login" -ForegroundColor Gray
        exit 1
    }
    Write-Host "✓ Auth token obtained" -ForegroundColor Green
} catch {
    Write-Host "✗ Error getting auth token: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Sending batch request to Cloud Function..." -ForegroundColor Yellow

# Build request body
$body = @{ name = $Pattern } | ConvertTo-Json

Write-Host "Request pattern: $Pattern" -ForegroundColor Cyan

try {
    $response = Invoke-WebRequest -Uri $FUNCTION_URL `
        -Method POST `
        -Headers @{
            "Authorization" = "Bearer $token"
            "Content-Type" = "application/json"
        } `
        -Body $body `
        -ErrorAction Stop
    
    Write-Host "✓ Function invoked successfully" -ForegroundColor Green
    Write-Host ""
    Write-Host "Response:" -ForegroundColor Cyan
    Write-Host $response.Content -ForegroundColor White
}
catch {
    Write-Host "✗ Error invoking function: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Waiting for processing to complete..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "Checking final BigQuery statistics..." -ForegroundColor Cyan
Write-Host ""

try {
    # Overall stats
    Write-Host "Total Statistics:" -ForegroundColor Yellow
    & bq --project_id=impasto-492602 query --use_legacy_sql=false `
      "SELECT COUNT(*) as total_items, COUNT(DISTINCT folio) as unique_invoices, COUNT(DISTINCT CASE WHEN es_duplicado = TRUE THEN folio END) as duplicate_invoices FROM logistica.facturas_raw" 2>$null
    
    Write-Host ""
    Write-Host "Recent Insertions (Last 10):" -ForegroundColor Yellow
    & bq --project_id=impasto-492602 query --use_legacy_sql=false `
      "SELECT nombre_archivo, estado_procesamiento, COUNT(*) as count FROM logistica.facturas_raw ORDER BY timestamp_procesamiento DESC LIMIT 10" 2>$null
    
}
catch {
    Write-Host "Note: BigQuery query failed, but data may still be processing." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== BATCH PROCESSING COMPLETE ===" -ForegroundColor Green
