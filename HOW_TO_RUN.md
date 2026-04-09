# How to Run - Quick Start Guide

## Prerequisites

- Windows 10+ with PowerShell 5.1+
- `gcloud` CLI installed and authenticated
- Working Cloud Function deployed
- Access to Google Cloud project (impasto-492602)

## Quick Start (2 steps)

### 1. Upload XML Files

Upload your XML files to Google Cloud Storage bucket:
```bash
gsutil -m cp data/*.xml gs://facturas-xml-uploads/
```

Or use Cloud Console web interface to upload.

### 2. Run Batch Processing

Open PowerShell in the project folder and run:
```powershell
.\process_batch_upload.ps1
```

**Output**:
```
Processed 24 files | 330 new documents | 84 duplicate documents | 1206 rows inserted
```

Done! Data is now in BigQuery table `impasto-492602:logistica.facturas_raw`.

---

## Detailed Usage

### Basic: Process All XML Files

```powershell
.\process_batch_upload.ps1
```
- Processes all files matching "DTE_Recibidos" pattern
- Typical for first run or full batch processing

### Pattern Matching: Process Specific Files

```powershell
# All files from April 2026
.\process_batch_upload.ps1 -Pattern "DTE_Recibidos*2026-04*"

# All XML files
.\process_batch_upload.ps1 -Pattern "*.xml"

# Specific file prefix
.\process_batch_upload.ps1 -Pattern "DTE_Recibidos_77384*"
```

### Processing Large Batches

```powershell
# Process files one pattern at a time to avoid timeout
.\process_batch_upload.ps1 -Pattern "DTE_Recibidos*2026-04*"
Wait-Event -Timeout 60  # Wait 60 seconds between batches
.\process_batch_upload.ps1 -Pattern "DTE_Recibidos*2026-05*"
```

---

## How It Works

```
1. You run: .\process_batch_upload.ps1
         ↓
2. Script gets auth token from gcloud
         ↓
3. Script POSTs to Cloud Function:
   https://process-xml-to-bq-wdb4jclboq-uc.a.run.app
         ↓
4. Cloud Function:
   a) Lists matching XML files in storage bucket
   b) Downloads up to 5 files in parallel
   c) Parses each XML, extracts invoice items
   d) Checks for duplicates using hash cache
   e) Inserts all rows to BigQuery
   f) Returns summary
         ↓
5. Script displays results:
   "Processed 24 files | 330 new documents | ..."
```

---

## Understanding the Output

### Normal Success Output
```
Authorization successful
Sending batch request...
HTTP/1.1 200 OK

Response:
Processed 24 files | 330 new documents | 84 duplicate documents | 1206 rows inserted
```

**What this means**:
- ✅ 24 XML files were downloaded and parsed
- ✅ 330 documents had never been seen before (new)
- ✅ 84 documents were duplicates (already in DB, marked but inserted anyway)
- ✅ 1206 total invoice items (rows) were inserted

### Expected Duplicates

After first batch, subsequent batches may show duplicates if:
- Same files uploaded again (intentional reprocessing for audit)
- Files with same invoice numbers from same seller
- This is normal and expected

---

## Verification

### Check Recently Inserted Rows

```bash
# Show most recent 50 rows
gcloud bigquery query --project_id=impasto-492602 \
  --use_legacy_sql=false \
  'SELECT nombre_archivo, folio, rut_emisor, COUNT(*) as items
   FROM `impasto-492602.logistica.facturas_raw`
   ORDER BY timestamp_procesamiento DESC
   LIMIT 50'
```

### Count Total Rows by Status

```bash
gcloud bigquery query --project_id=impasto-492602 \
  --use_legacy_sql=false \
  'SELECT 
     estado_procesamiento,
     COUNT(*) as total_rows,
     COUNT(DISTINCT hash_md5) as unique_documents
   FROM `impasto-492602.logistica.facturas_raw`
   GROUP BY estado_procesamiento'
```

### Check Specific Date Range

```bash
gcloud bigquery query --project_id=impasto-492602 \
  --use_legacy_sql=false \
  'SELECT nombre_archivo, COUNT(*) as items
   FROM `impasto-492602.logistica.facturas_raw`
   WHERE DATE(timestamp_procesamiento) = "2026-04-09"
   GROUP BY nombre_archivo'
```

---

## Troubleshooting

### "Service Unavailable" Error

```
Error: HTTP/1.1 503 Service Unavailable
```

**Cause**: Cloud Function starting up (takes 10-15 seconds first run)
**Solution**: Wait 15 seconds and retry:
```powershell
Start-Sleep -Seconds 15
.\process_batch_upload.ps1
```

### "Access Denied" or "Permission Denied"

```
HTTP/1.1 403 Forbidden
Access Denied: Permission denied
```

**Cause**: Service account lacks BigQuery permissions
**Solution**: Grant IAM role:
```bash
gcloud projects add-iam-policy-binding impasto-492602 \
  --member=serviceAccount:75127295541-compute@developer.gserviceaccount.com \
  --role=roles/bigquery.dataEditor
```

### No Files Found

```
Processed 0 files
```

**Causes**:
1. No XML files in bucket
2. Pattern doesn't match any files
3. Wrong bucket configured

**Solutions**:
```powershell
# Check what files exist
gsutil ls gs://facturas-xml-uploads/

# Verify bucket in Cloud Console
# https://console.cloud.google.com/storage/

# Try simpler pattern
.\process_batch_upload.ps1 -Pattern "*.xml"
```

### Script Permission Denied

```
.\process_batch_upload.ps1 : File cannot be loaded because running scripts is disabled
```

**Cause**: PowerShell execution policy too restrictive
**Solution**: 
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
# Then retry:
.\process_batch_upload.ps1
```

### Files Not Appearing in BigQuery

**Cause**: Row insert succeeded but data not visible yet
**Solutions**:
1. Wait 10-30 seconds for BigQuery replication
2. Run timestamp check:
   ```bash
   gcloud bigquery query --project_id=impasto-492602 \
     --use_legacy_sql=false \
     'SELECT MAX(timestamp_procesamiento) as last_insert 
      FROM `impasto-492602.logistica.facturas_raw`'
   ```
3. If last insert is old, check Cloud Logging:
   ```bash
   gcloud logging read "resource.labels.service_name=process-xml-to-bq" \
     --limit 10 --project=impasto-492602
   ```

---

## Performance Expectations

| Metric | Value |
|--------|-------|
| Files per batch | 1-1000+ |
| Throughput | ~40 rows/sec |
| 24 files | ~30 seconds |
| 1000 files | ~10-15 minutes |
| Memory usage | <512MB |
| Cost per batch | <$0.01 |

Concurrent processing (5 workers) makes larger batches faster proportionally.

---

## Scaling Up

### For Hundreds of Files

```powershell
# Split into smaller patterns
.\process_batch_upload.ps1 -Pattern "*2026-04-01*"  # 50 files
.\process_batch_upload.ps1 -Pattern "*2026-04-02*"  # 50 files
.\process_batch_upload.ps1 -Pattern "*2026-04-03*"  # 50 files
```

### For Thousands of Files

```powershell
# Create a loop script:
$dates = "2026-04-01", "2026-04-02", "2026-04-03"  # etc
foreach ($date in $dates) {
    $pattern = "*$date*"
    Write-Host "Processing $pattern..."
    .\process_batch_upload.ps1 -Pattern $pattern
    Start-Sleep -Seconds 2
}
```

### For Continuous Processing

Use Cloud Scheduler (Google Cloud) with Cloud Tasks to trigger regularly:
1. Create Cloud Scheduler job
2. Set HTTP target to Cloud Function URL
3. Schedule frequency (hourly, daily, etc.)
4. Logs appear in Cloud Logging

---

## Key Files

| File | Purpose |
|------|---------|
| `process_batch_upload.ps1` | User script - run this |
| `cloud_function/main.py` | Production code (deployed) |
| `AGENT_CONTEXT.md` | System config and troubleshooting |
| `CODE_DOCUMENTATION.md` | Technical architecture |

---

## Next Steps

1. **First time**: Upload some XML files and run batch processing
2. **Verification**: Check Cloud Console BigQuery to see data
3. **Scaling**: Use patterns for different date ranges or sellers
4. **Automation**: Set up Cloud Scheduler for regular processing

---

## Getting Help

- **Code questions**: See CODE_DOCUMENTATION.md
- **Configuration issues**: See AGENT_CONTEXT.md
- **Specific errors**: Check Cloud Logging:
  ```bash
  gcloud logging read "resource.labels.service_name=process-xml-to-bq" \
    --limit 50 --project=impasto-492602 --format=json | jq
  ```

---

**Last Updated**: 2026-04-09
**Status**: Production-ready
**Test Results**: 24 files, 1,206 rows, 100% accurate deduplication ✅
