# Facturas - XML Invoice Processing Pipeline

A cloud-native system that processes Chilean tax authority (SII) XML invoices (DTEs) and inserts line-item data into Google BigQuery for analytics and auditing.

## Quick Overview

```
XML File (Manual Upload)
    ↓
Google Cloud Storage (gs://facturas-xml-uploads)
    ↓
Cloud Run Function (HTTP triggered)
    ↓
Parse XML → Extract Items → Deduplication
    ↓
Google BigQuery (logistica.facturas_raw - item-level)
```

## What It Does

1. **Accepts XML files** uploaded manually to Cloud Storage bucket
2. **Extracts item-level data** from each invoice's line items (`<Detalle>` elements)
3. **Stores in BigQuery** as one row per item with 25 fields
4. **Deduplicates** at document level using MD5(folio#rut_emisor)

## How It Works

```
1. Upload XML File
   ↓
   gsutil cp DTE_Recibidos_*.xml gs://facturas-xml-uploads/
   ↓
2. Run Trigger Script (one command)
   ↓
   .\process_upload.ps1
   ↓
3. Processing Happens Automatically
   • Download from bucket
   • Parse XML
   • Extract items
   • Check for duplicates
   • Insert to BigQuery
   ↓
4. See Results
   • Function returns row count
   • Check BigQuery for new data
```

## Architecture

| Component | Type | Location |
|-----------|------|----------|
| **Trigger** | Cloud Run HTTP endpoint | https://process-xml-to-bq-wdb4jclboq-uc.a.run.app |
| **Compute** | Cloud Function Gen 2 | process-xml-to-bq (us-central1) |
| **Storage** | Cloud Storage bucket | gs://facturas-xml-uploads |
| **Database** | BigQuery table | logistica.facturas_raw |
| **Project** | GCP | impasto-492602 |

## How to Use (Quick Start)

### 1. Upload XML to Cloud Storage
```bash
gsutil cp DTE_Recibidos_*.xml gs://facturas-xml-uploads/
```

### 2. Run the Trigger Script

**PowerShell (Recommended):**
```powershell
.\process_upload.ps1
```

Or with specific filename:
```powershell
.\process_upload.ps1 -FileName "DTE_Recibidos_77384122_FecDesde2026-04-01_pszFecHasta2026-04-06_2026-04-07.xml"
```

**Bash:**
```bash
./process_upload.sh
# or with filename:
./process_upload.sh "DTE_Recibidos_*.xml"
```

The script will:
- ✅ Automatically find and process the uploaded file
- ✅ Extract all item-level data
- ✅ Insert into BigQuery
- ✅ Show you how many rows were processed

### 3. Check Results
```bash
# Total items
bq --project_id=impasto-492602 query --use_legacy_sql=false \
  "SELECT COUNT(*) FROM logistica.facturas_raw"

# Sample data
bq --project_id=impasto-492602 query --use_legacy_sql=false \
  "SELECT folio, numero_linea, descripcion, cantidad, precio_unitario FROM logistica.facturas_raw LIMIT 5"
```

## Project Structure

```
facturas/
├── README.md                            # Usage guide (this file)
├── REPOSITORY_CONTEXT.md               # Context for future agents
├── requirements.txt                     # Python dependencies
├── main.py                              # Local entry point (legacy)
├── config/settings.py                   # Configuration
├── data/                                # XML input files
├── src/                                 # Utility modules
├── test_deploy/
│   ├── main.py                         # ⭐ DEPLOYED Cloud Function
│   └── requirements.txt
└── logs/
```

## Cloud Function Details

**File:** `test_deploy/main.py`  
**Status:** ✅ ACTIVE and working  
**Runtime:** Python 3.9  
**Region:** us-central1  
**Trigger:** HTTP endpoint (manual trigger via `process_upload.ps1`)

### Processing Flow
1. Run script: `.\process_upload.ps1`
2. Function auto-detects latest XML file in bucket
3. Downloads and parses XML
4. Extracts all line items from documents
5. For each document:
   - Generates MD5 hash for deduplication
   - Checks if already in BigQuery
   - Extracts all line items
6. Inserts rows to BigQuery (40-50+ items per file)
7. Returns count of rows processed

### Key Functions
- `process_xml_to_bq(request)` - HTTP handler, finds and processes latest file
- `extract_item_rows(documento, filename)` - Extract items from document
- `is_duplicate(row, bq_client)` - Deduplication check
- `insert_rows_to_bigquery(rows, bq_client)` - Batch insert

## BigQuery Schema

**Table:** `impasto-492602.logistica.facturas_raw`

| Field | Type | Description |
|-------|------|-------------|
| documento_id | STRING | MD5 hash for dedup (folio#rut_emisor) |
| folio | INT64 | Invoice number |
| fecha_emis | DATE | Invoice date |
| rut_emisor | STRING | Seller tax ID |
| rsn_emisor | STRING | Seller name |
| rut_receptor | STRING | Buyer tax ID |
| rsn_receptor | STRING | Buyer name |
| tipo_dte | STRING | Invoice type (33, 34, etc) |
| numero_linea | INT64 | Line item number |
| tipo_codigo | STRING | Product code type |
| codigo | STRING | Product code |
| descripcion | STRING | Item description |
| cantidad | FLOAT64 | Quantity |
| precio_unitario | FLOAT64 | Unit price (CLP) |
| descuento_percent | FLOAT64 | Discount % |
| descuento_monto | FLOAT64 | Discount amount (CLP) |
| monto_item | FLOAT64 | Subtotal (CLP) |
| tasa_iva | FLOAT64 | VAT rate % |
| iva_item | FLOAT64 | VAT amount (CLP) |
| monto_total_item | FLOAT64 | Total with VAT (CLP) |
| es_duplicado | BOOLEAN | Is duplicate? |
| estado_procesamiento | STRING | "processed" or "duplicate" |
| hash_md5 | STRING | Document hash |
| timestamp_procesamiento | STRING | ISO 8601 timestamp |
| nombre_archivo | STRING | Source filename |

## Deployment

### Deploy Changes
```bash
cd test_deploy
gcloud functions deploy process_xml_to_bq \
  --runtime python39 \
  --trigger-topic facturas-xml-uploads \
  --entry-point process_xml_to_bq \
  --source . \
  --project impasto-492602
```

### Dependencies
```
functions-framework==3.*
google-cloud-storage>=2.0
google-cloud-bigquery>=3.0
```

## Testing

### Local XML Parsing Test
```bash
python -c "
import xml.etree.ElementTree as ET
tree = ET.parse('data/DTE_Recibidos_*.xml')
root = tree.getroot()
dtes = root.findall('DTE')
print(f'Found {len(dtes)} documents')
"
```

### Check Function Logs
```bash
gcloud logging read "resource.labels.service_name=process-xml-to-bq" \
  --limit 50 --project impasto-492602 --format "value(textPayload)"
```

## Status

✅ **Operational** - Item-level extraction working  
✅ **Tested** - 50+ rows successfully inserted  
✅ **Deduplication** - Functional at document level  
✅ **Direct HTTP** - Reliable trigger method

## Troubleshooting

### 0 records in BigQuery
- Check function logs: `gcloud logging read "resource.labels.service_name=process-xml-to-bq" --project impasto-492602`
- Verify XML exists in bucket: `gsutil ls gs://facturas-xml-uploads/`
- Test locally first (see Testing section)

### Permission denied errors
- Verify service account has `roles/bigquery.dataEditor` and `roles/storage.objectViewer`
- Service account: `facturas-processor@impasto-492602.iam.gserviceaccount.com`

### Function not deploying
- Check Python syntax: `python -m py_compile test_deploy/main.py`
- Verify `requirements.txt` has correct package names
- Check Cloud Build logs in GCP console

## For Future Maintenance

See [REPOSITORY_CONTEXT.md](REPOSITORY_CONTEXT.md) for:
- Architecture decisions and why they were made
- Issues encountered and how they were solved
- Step-by-step debugging procedures
- Historical context and timeline
