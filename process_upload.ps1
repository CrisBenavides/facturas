# process_upload.ps1 - Trigger processing of uploaded XML files
# Usage: .\process_upload.ps1 -FileName "DTE_Recibidos_*.xml"
#   or:  .\process_upload.ps1 (processes latest file)

param(
    [string]$FileName
)

$FUNCTION_URL = "https://us-central1-impasto-492602.cloudfunctions.net/process_xml_to_bq"

# Get auth token
Write-Host "Getting auth token..." -ForegroundColor Yellow
$token = & gcloud auth print-identity-token

if ([string]::IsNullOrEmpty($FileName)) {
    Write-Host "Processing latest XML file in bucket..." -ForegroundColor Green
    $body = @{} | ConvertTo-Json
} else {
    Write-Host "Processing: $FileName" -ForegroundColor Green
    $body = @{ name = $FileName } | ConvertTo-Json
}

Write-Host "Invoking function..." -ForegroundColor Yellow
$response = Invoke-WebRequest -Uri $FUNCTION_URL `
    -Method POST `
    -Headers @{
        "Authorization" = "Bearer $token"
        "Content-Type" = "application/json"
    } `
    -Body $body

Write-Host "Response: $($response.StatusCode) - $($response.Content)" -ForegroundColor Cyan

Write-Host "Waiting for processing..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host "Checking BigQuery for new rows..." -ForegroundColor Cyan
bq --project_id=impasto-492602 query --use_legacy_sql=false `
  "SELECT COUNT(*) as total_rows, COUNT(DISTINCT folio) as invoices FROM logistica.facturas_raw"
