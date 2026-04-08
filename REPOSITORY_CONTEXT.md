# Repository Context for Future Developers

This document provides historical context, architecture decisions, and debugging information for maintaining this project.

## Project Genesis

**Original Goal:** Web scrape Chilean SII (tax authority) website for invoice PDFs

**Pivoted to:** Manual XML upload + cloud processing pipeline (more reliable, no web scraping)

**Current Implementation:** Item-level invoice processing in Google Cloud Platform

---

## Architecture Journey

### Phase 1: Local Web Scraper (ABANDONED)
- Attempted to scrape SII.cl directly
- Issues: CAPTCHAs, session management, dynamic rendering
- **Decision:** Too fragile and violates SII terms

### Phase 2: Local XML Processor (WORKING LOCALLY)
- User switched to manual XML uploads
- Built `XMLProcessor` class to parse local XML files
- Fixed parser to extract ALL `<DTE>` elements (not just first)
- Output maintained XML structure: SetDTE → DTE → Documento

### Phase 3: GCP Migration (CURRENT - PRODUCTION)
- Migrated to Google Cloud Platform (project: impasto-492602)
- **Why?** Scalability, built-in data warehouse, serverless architecture
- Components:
  - Cloud Storage bucket: gs://facturas-xml-uploads
  - BigQuery dataset: logistica
  - Cloud Functions Gen 2 (Python 3.9)
  - Service account: facturas-processor@impasto-492602.iam.gserviceaccount.com

---

## Key Technical Decisions & Lessons Learned

### 1. Document-Level → Item-Level Schema Change
**Problem:** Originally stored one row per invoice, but user needed granular item data

**Solution:** Refactored to extract each `<Detalle>` element as a separate row

**Result:** 50+ rows from 20 invoices (instead of 20 rows)

**BigQuery Table:** Now has 25 fields including item-level details

### 2. Module-Level GCP Client Initialization ❌ → Lazy Loading ✅
**Problem:** Initializing `storage.Client()` at module level caused container startup failure
```python
# BAD - causes startup failure
from google.cloud import storage
client = storage.Client()  # ← Dies during Cloud Run container start
```

**Solution:** Initialize clients inside function body
```python
# GOOD - lazy loading
def process_xml_to_bq(request):
    from google.cloud import storage
    client = storage.Client()  # ← Initialized on demand
```

**Why:** Cloud Run containers need to start fast and listen on PORT=8080 before clients are needed

### 3. Pub/Sub vs Direct HTTP Triggers
**Initial Attempt:** Pub/Sub triggers for automatic processing

**Challenges Encountered:**
- JSON message format issues (quotes getting stripped during CLI parsing)
- Eventarc subscription required (auto-created but complex)
- Multiple encoding layers can corrupt data
- Silent failures without clear error messages

**Solution: Simple HTTP Endpoint + Manual Trigger Script**
- HTTP endpoint is reliable and easy to debug
- User runs `process_upload.ps1` script after uploading
- One-command trigger (simple and transparent)
- No complex event routing
- Full visibility into what's processing

**Why This Works Better:**
- ✅ No JSON encoding issues
- ✅ Immediate feedback (shows row count)
- ✅ Can be called from any script/schedule
- ✅ User has full control
- ✅ Already tested and working (processed 46 rows successfully)

**Status:** ✅ PRODUCTION READY - Simple, reliable approach

### 4. Deduplication Strategy
**Decision:** MD5(folio#rut_emisor) as document-level unique key

**Why?**
- Folio (invoice number) + RUT (seller tax ID) uniquely identifies a document
- MD5 provides efficient lookup in BigQuery
- Prevents duplicate processing of same invoice

**Implementation:**
```python
hash_key = f"{folio}#{rut_emisor}"
hash_documento = hashlib.md5(hash_key.encode()).hexdigest()
```

---

## Major Issues Encountered & Resolutions

### Issue 1: Container Startup Failure (25+ Deployment Attempts)
**Error:** `Container failed to start and listen on PORT=8080`

**Root Cause:** Module-level GCP client initialization blocked startup

**Resolution:** Implemented lazy-loading of clients inside function

**Lesson:** Cloud Functions need minimal startup time before listening to port

---

### Issue 2: Pub/Sub Authentication Failures (403 Errors)
**Error:** `The request was not authenticated`

**Root Cause:** Service account lacked `roles/run.invoker` permission

**Resolution:** 
1. Granted `roles/run.invoker` to service account
2. Also granted to Pub/Sub service agent

**Lesson:** Service accounts need explicit invocation permissions, not just data permissions

---

### Issue 3: Schema Mismatch After Refactoring
**Problem:** Changed from document-level (17 fields) to item-level (25 fields) schema

**Initial Mistake:** Created new table `facturas_items` instead of reusing `facturas_raw`

**Resolution:** 
1. Deleted old `facturas_raw` (document-level)
2. Created new `facturas_raw` with item-level schema
3. Updated code to use same TABLE_ID

**Result:** ✅ 50+ rows successfully inserted

---

### Issue 4: JSON Message Format Corruption
**Problem:** Pub/Sub messages had malformed JSON: `{bucket:...,name:...}` (no quotes on keys)

**Cause:** PowerShell/bash shell interpretation of quotes during `gcloud pubsub topics publish`

**Solutions Tried:**
1. ❌ Direct string parameter
2. ❌ Base64 encoding in CLI
3. ✅ Write JSON to file, then read from file
4. ✅ Use direct HTTP invocation instead (best solution)

**Lesson:** Shell quote handling is tricky; use files or HTTP when possible

---

## GCP Resource Details

### Service Account
- **Email:** `facturas-processor@impasto-492602.iam.gserviceaccount.com`
- **Roles:**
  - `roles/bigquery.dataEditor` (insert rows)
  - `roles/storage.objectViewer` (download XML)
  - `roles/run.invoker` (invoke Cloud Run)

### Cloud Storage Bucket
- **Name:** `gs://facturas-xml-uploads`
- **Region:** us-central1
- **Lifecycle:** None (files persist indefinitely)

### BigQuery Dataset
- **Project:** impasto-492602
- **Dataset:** logistica
- **Table:** facturas_raw (25 fields, item-level)
- **Rows:** 50+ (from testing with 20 invoice documents)

### Cloud Function
- **Service:** process-xml-to-bq
- **Runtime:** Python 3.9
- **Region:** us-central1
- **Type:** HTTP endpoint (triggered manually via script)
- **Status:** ✅ ACTIVE and working
- **HTTP Endpoint:** https://us-central1-impasto-492602.cloudfunctions.net/process_xml_to_bq

### Trigger Script
- **File:** `process_upload.ps1` (PowerShell)
- **Alternative:** `process_upload.sh` (Bash)
- **Usage:** Run after uploading XML files
- **Function:** Automatically detects latest file or processes specified file

---

## Data Model

### XML Structure Expected
```xml
<SetDTE>
  <DTE>
    <Documento>
      <Encabezado>
        <IdDoc>
          <Folio>2810</Folio>
          <TipoDTE>33</TipoDTE>
          <FchEmis>2026-04-01</FchEmis>
        </IdDoc>
        <Emisor>
          <RUTEmisor>77-3</RUTEmisor>
          <RznSoc>Brewery</RznSoc>
        </Emisor>
        <Receptor>
          <RUTRecep>12-3</RUTRecep>
          <RznSocRecep>Bar</RznSocRecep>
        </Receptor>
      </Encabezado>
      <Detalle>
        <NroLinDet>1</NroLinDet>
        <NmbItem>Summer ale</NmbItem>
        <QtyItem>2</QtyItem>
        <PrcItem>35600</PrcItem>
        <MontoItem>71200</MontoItem>
        <TasaIVA>19</TasaIVA>
        <IVAItem>13528</IVAItem>
      </Detalle>
      <!-- More Detalle elements -->
    </Documento>
  </DTE>
  <!-- More DTE elements -->
</SetDTE>
```

### Extraction Logic
- One row per `<Detalle>` element
- Header info (folio, seller, buyer, etc) duplicated across items for same document
- Flat structure in BigQuery (not nested)

---

## Code Quality & Future Improvements

### Technical Debt
- Python 3.9 runtime is deprecated (upgrade to 3.11+)
- Minimal error handling (should add retry logic)
- No monitoring/alerting setup
- Limited logging (adequate for current testing)

### TODO Items
1. **Migrate Python runtime** from 3.9 → 3.11
2. **Add monitoring** with Cloud Logging alerts
3. **Implement retry logic** for transient failures
4. **Cache deduplication check** (currently queries BigQuery each time)
5. **Batch optimization** (could increase insert batch size)
6. **Document XML variations** across different years/DTE types

### Performance Notes
- Current implementation: ~50 rows per file, <5 second execution
- BigQuery inserts are very fast (batch API)
- XML parsing is bottleneck if files are very large (100k+ items)

---

## Testing & Debugging Procedures

### Manual Function Invocation (Recommended for Testing)

**PowerShell:**
```powershell
$token = gcloud auth print-identity-token
$message = '{"bucket":"facturas-xml-uploads","name":"DTE_Recibidos_*.xml"}'
$data = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($message))
$body = @{ message = @{ data = $data } } | ConvertTo-Json

Invoke-WebRequest -Uri "https://process-xml-to-bq-wdb4jclboq-uc.a.run.app" `
  -Method POST `
  -Headers @{"Authorization" = "Bearer $token"; "Content-Type" = "application/json"} `
  -Body $body

# Wait and check
Start-Sleep -Seconds 5
bq --project_id=impasto-492602 query --use_legacy_sql=false "SELECT COUNT(*) FROM logistica.facturas_raw"
```

### Local XML Parsing Test
```bash
python -c "
import xml.etree.ElementTree as ET
tree = ET.parse('data/DTE_Recibidos_*.xml')
root = tree.getroot()
dtes = root.findall('DTE')
print(f'Found {len(dtes)} documents')
for dte in dtes[:1]:
    doc = dte.find('Documento')
    detalles = doc.findall('Detalle')
    print(f'First doc has {len(detalles)} items')
"
```

### Check Function Logs
```bash
# Recent errors
gcloud logging read "resource.labels.service_name=process-xml-to-bq" \
  --limit 20 --project impasto-492602 | grep ERROR

# Full trace
gcloud logging read "resource.labels.service_name=process-xml-to-bq" \
  --limit 100 --project impasto-492602 --format "value(textPayload)"
```

### Verify BigQuery Data
```bash
# Total stats
bq --project_id=impasto-492602 query --use_legacy_sql=false \
  "SELECT COUNT(*) as items, COUNT(DISTINCT folio) as invoices FROM logistica.facturas_raw"

# Sample items
bq --project_id=impasto-492602 query --use_legacy_sql=false \
  "SELECT * FROM logistica.facturas_raw LIMIT 5"

# Check for duplicates
bq --project_id=impasto-492602 query --use_legacy_sql=false \
  "SELECT COUNT(*) FROM logistica.facturas_raw WHERE es_duplicado = TRUE"
```

---

## Deployment Checklist

### When Deploying Code Changes
- [ ] Test locally: `python test_deploy/main.py` (if function can be called locally)
- [ ] Check syntax: `python -m py_compile test_deploy/main.py`
- [ ] Update `test_deploy/requirements.txt` if adding dependencies
- [ ] Run: `gcloud functions deploy process_xml_to_bq ...`
- [ ] Wait for deployment to complete (check GCP console)
- [ ] Test with manual invocation (see Testing section)
- [ ] Check function logs for errors
- [ ] Verify BigQuery has new records

### When Modifying Schema
- [ ] **BACKUP** current BigQuery table (export to GCS)
- [ ] Test schema changes locally with sample XML
- [ ] Create new BigQuery table with new schema
- [ ] Update TABLE_ID in `test_deploy/main.py`
- [ ] Deploy function
- [ ] Verify inserts work
- [ ] Delete old table only after confirming new one works

---

## Contact & Questions

- **GCP Project:** impasto-492602
- **Service Account:** facturas-processor@impasto-492602.iam.gserviceaccount.com
- **Cloud Function:** process-xml-to-bq (Cloud Run)
- **BigQuery:** logistica.facturas_raw

For issues, check:
1. Cloud Logging (recent errors)
2. GCP IAM permissions (service account roles)
3. BigQuery table schema (compare with code expectations)
4. XML file format (validate against expected structure)

---

## Appendix: Key Files

- **Cloud Function Code:** [test_deploy/main.py](test_deploy/main.py)
- **Dependencies:** [test_deploy/requirements.txt](test_deploy/requirements.txt)
- **Usage Guide:** [README.md](README.md)
- **Local XML Sample:** [data/DTE_Recibidos_*.xml](data/)
