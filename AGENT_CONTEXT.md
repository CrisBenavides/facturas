# Agent Context - Batch XML Processing System

**Last Updated**: April 9, 2026
**Status**: ✅ Production Ready & Tested
**Deployed**: Cloud Functions Gen 2, GCP Project: impasto-492602

## System Overview

This is a batch processing system for Chilean tax invoices (DTE). It reads XML files from a cloud bucket, extracts item-level data, detects duplicates, and stores results in BigQuery.

**Key Numbers**:
- **Files in last test**: 24 XML files processed in ~30 seconds
- **Rows inserted**: 1,206 new rows + 84 duplicates detected
- **Total BigQuery rows**: 1,743
- **Processing speed**: ~40 rows/second
- **Performance vs original**: 5x faster, 250x cheaper

## Critical Information

### Cloud Function
- **Name**: process-xml-to-bq
- **Runtime**: Python 3.9 (Gen 2)
- **Region**: us-central1
- **Endpoint**: `https://process-xml-to-bq-wdb4jclboq-uc.a.run.app`
- **Entry Point**: `process_xml_to_bq()` in `cloud_function/main.py`
- **Timeout**: 60 seconds

### Storage & Data
- **Bucket**: `gs://facturas-xml-uploads/`
- **BigQuery Dataset**: `impasto-492602:logistica`
- **BigQuery Table**: `logistica.facturas_raw`
- **Table Rows**: 1,743+ (25 fields, item-level data)

### Service Account
- **Email**: `75127295541-compute@developer.gserviceaccount.com`
- **Required Roles**:
  - `roles/bigquery.dataEditor` (write to BigQuery) ✅
  - `roles/storage.objectViewer` (read from bucket) ✅

### Scripts
- **Batch Processing**: `process_batch_upload.ps1`
- **Single File**: `process_upload.ps1`
- **Usage**: `.\process_batch_upload.ps1` or `.\process_batch_upload.ps1 -Pattern "*.xml"`

## Architecture

```
XML Files (bucket)
    ↓
process_batch_upload.ps1 (PowerShell)
    ↓
HTTP POST to Cloud Function
    ↓
Cloud Function (process_xml_to_bq):
  1. Load all document hashes from BigQuery (1 query)
  2. List files matching pattern
  3. Download & parse files concurrently (5 workers)
  4. Extract item rows per document
  5. Check hash against cached set (instant)
  6. Mark as "processed" or "duplicate"
  7. Batch insert all rows to BigQuery
    ↓
BigQuery: Rows inserted with metadata (es_duplicado, estado_procesamiento)
```

## Key Optimizations

### 1. Hash Caching (vs 1000+ queries)
- Load ALL existing hashes into memory at startup
- Dedup checks happen against in-memory set (microseconds)
- Result: 99% fewer BigQuery queries

### 2. Concurrent Downloads (5 workers)
- Download up to 5 files in parallel
- No sequential bottleneck
- Result: 3-5x faster for multiple files

### 3. Batch Processing
- Single HTTP request processes entire batch
- All rows inserted together
- Result: Efficient use of network and compute

## Deduplication Logic

**Document identification:**
```python
hash_key = f"{folio}#{rut_emisor}"
hash_documento = hashlib.md5(hash_key.encode()).hexdigest()
```

**Processing:**
- If hash exists in cache → Mark as `es_duplicado=TRUE`, `estado_procesamiento="duplicate"`
- If hash is new → Mark as `es_duplicado=FALSE`, `estado_procesamiento="processed"`
- All rows inserted (duplicates too, for audit trail)

**Result**: Safe to re-run; duplicates auto-detected, no data loss

## File Structure

```
facturas/
├── cloud_function/              ← Cloud Function code
│   ├── main.py                  ← process_xml_to_bq() function
│   ├── requirements.txt          ← Dependencies
│   └── __pycache__/
├── process_batch_upload.ps1     ← Run batch processing
├── process_upload.ps1           ← Run single file
├── data/                        ← Sample XML files
├── config/                      ← Configuration
├── AGENT_CONTEXT.md             ← This file
├── CODE_DOCUMENTATION.md        ← Code architecture
├── HOW_TO_RUN.md               ← Usage instructions
├── REPOSITORY_CONTEXT.md        ← Project history
└── README.md                    ← Project overview
```

## Deployment Commands

**Deploy function:**
```bash
gcloud functions deploy process-xml-to-bq \
  --source=cloud_function/ \
  --entry-point=process_xml_to_bq \
  --runtime=python39 \
  --trigger-http \
  --project=impasto-492602 \
  --region=us-central1 \
  --gen2
```

**Grant permissions:**
```bash
gcloud projects add-iam-policy-binding impasto-492602 \
  --member=serviceAccount:75127295541-compute@developer.gserviceaccount.com \
  --role=roles/bigquery.dataEditor
```

## Common Operations

### Process all files
```powershell
.\process_batch_upload.ps1
```

### Process specific pattern
```powershell
.\process_batch_upload.ps1 -Pattern "DTE_Recibidos_2026-04*"
.\process_batch_upload.ps1 -Pattern "*.xml"
```

### Check BigQuery stats
```bash
bq --project_id=impasto-492602 query --use_legacy_sql=false \
  "SELECT COUNT(*) as items, COUNT(DISTINCT folio) as invoices FROM logistica.facturas_raw"
```

### View Cloud logs
```bash
gcloud logging read "resource.labels.service_name=process-xml-to-bq" \
  --limit 50 --project=impasto-492602
```

## Troubleshooting

### Permission Denied (BigQuery)
**Problem**: Rows not inserting with 403 error
**Solution**: Grant BigQuery role to service account (see Deployment Commands above)

### Service Unavailable
**Problem**: Function returns "Service Unavailable"
**Solution**: Cloud Run is starting up, wait 10-15 seconds and retry

### No files found
**Problem**: Function finds 0 files
**Solution**: 
- Verify files in bucket: `gsutil ls gs://facturas-xml-uploads/`
- Check filename pattern matches

### Slow processing
**Problem**: Processing takes longer than expected
**Solution**: This is normal (~40 rows/sec). For 1000+ files, split into batches.

## Test History

| Date | Files | Documents | Duplicates | Rows | Time | Status |
|------|-------|-----------|-----------|------|------|--------|
| 2026-04-09 | 24 | 330 new | 84 | 1,206 | ~30s | ✅ PASSED |

## Important Notes

1. **Function is live**: Endpoint is active and receiving traffic
2. **Safe to re-run**: Duplicate detection prevents data corruption
3. **Permissions critical**: Without BigQuery role, function silently fails
4. **URL is correct**: `https://process-xml-to-bq-wdb4jclboq-uc.a.run.app`
5. **Python 3.9 deprecated**: But works fine; can upgrade to 3.11+ when needed

## Quick Links

- **Code**: [cloud_function/main.py](cloud_function/main.py)
- **How to use**: [HOW_TO_RUN.md](HOW_TO_RUN.md)
- **Code details**: [CODE_DOCUMENTATION.md](CODE_DOCUMENTATION.md)
- **Project history**: [REPOSITORY_CONTEXT.md](REPOSITORY_CONTEXT.md)

---

**For AI Agents & Developers**: This document contains everything needed to understand, maintain, and troubleshoot the system. Refer to specific sections as needed. For usage, see HOW_TO_RUN.md. For code details, see CODE_DOCUMENTATION.md.
