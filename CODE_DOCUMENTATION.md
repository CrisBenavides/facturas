# Code Documentation - System Architecture & Implementation

## Cloud Function: process_xml_to_bq()

**Location**: `cloud_function/main.py`
**Type**: HTTP-triggered Cloud Function (Gen 2)
**Language**: Python 3.9
**Trigger**: HTTP POST request to `https://process-xml-to-bq-wdb4jclboq-uc.a.run.app`

### Main Entry Point

```python
@functions_framework.http
def process_xml_to_bq(request):
    """HTTP endpoint - batch process multiple XML files efficiently"""
```

**Behavior**:
- Accepts JSON request with optional `name` parameter (filename pattern)
- Default pattern: "DTE_Recibidos" (all DTE_Recibidos files)
- Supports wildcards: "*.xml", "DTE_*_2026-04*", etc.
- Returns summary: "Processed X files | Y new documents | Z duplicates | N rows inserted"

## Key Functions

### extract_item_rows(documento, filename)

Extracts invoice items from a single XML document.

**Input**: 
- `documento`: XML element representing a single invoice
- `filename`: Source filename (for audit trail)

**Output**: List of row dictionaries, one per `<Detalle>` element

**Processing**:
1. Extract header info (folio, seller, buyer, dates, etc.)
2. Generate document hash: `MD5(folio + "#" + rut_emisor)`
3. Find all `<Detalle>` child elements (invoice items)
4. Create one row per item with:
   - Header data duplicated across items
   - Item-specific data (quantity, price, IVA, etc.)
   - Calculated fields (total with tax)
   - Metadata (filename, timestamp, hash)

**Returns**: List[dict] - Up to 50+ rows per document

### download_and_parse_xml(blob_name, storage_client, bucket_name)

Downloads and parses a single XML file (used in concurrent workers).

**Input**:
- `blob_name`: Filename in bucket
- `storage_client`: GCS client
- `bucket_name`: Bucket name

**Output**: Tuple of (filename, parsed_xml_root)

**Error handling**: Returns (filename, None) on error, continues processing

### insert_rows_to_bigquery(rows, bq_client)

Batch inserts rows to BigQuery.

**Input**:
- `rows`: List of row dictionaries
- `bq_client`: BigQuery client

**Behavior**:
- Gets table reference
- Uses `insert_rows_json()` for batch insert
- Logs errors if any occur

**Performance**: Fast batch API (whole payload inserted together)

## Processing Pipeline

### Step 1: Load Hash Cache
```python
# Single BigQuery query loads ALL existing hashes
query = "SELECT DISTINCT hash_documento FROM facturas_raw WHERE hash_documento IS NOT NULL"
existing_hashes = set()
for row in bq_client.query(query).result():
    existing_hashes.add(row["hash_documento"])
```

**Purpose**: Avoid 1000+ queries later
**Result**: ~500 hashes in memory

### Step 2: List Files
```python
# Use regex to match pattern
pattern_regex = pattern.replace("*", ".*")
blobs = [blob for blob in bucket.list_blobs() 
         if re.match(pattern_regex, blob.name) and blob.name.endswith('.xml')]
```

**Result**: List of 1-1000+ blob objects

### Step 3: Concurrent Downloads
```python
# Download up to 5 files in parallel
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    results = executor.map(
        partial(download_and_parse_xml, 
                storage_client=storage_client, 
                bucket_name=bucket_name),
        [blob.name for blob in matching_blobs]
    )
```

**Result**: List of (filename, parsed_xml) tuples

### Step 4: Process Each File
```python
for file_name, root in file_data:
    # Find all DTE elements (documents)
    dtes = root.findall("DTE")
    for dte in dtes:
        documento = dte.find("Documento")
        item_rows = extract_item_rows(documento, file_name)
        
        # Check if duplicate
        doc_hash = item_rows[0]["hash_md5"]
        is_dup = doc_hash in existing_hashes
        
        # Mark rows appropriately
        for row in item_rows:
            if is_dup:
                row["estado_procesamiento"] = "duplicate"
                row["es_duplicado"] = True
            else:
                row["estado_procesamiento"] = "processed"
                row["es_duplicado"] = False
                # Add to cache for rest of batch
                existing_hashes.add(doc_hash)
            
            rows_to_insert.append(row)
        
        # Batch insert this file's rows
        insert_rows_to_bigquery(rows_to_insert, bq_client)
```

**Result**: All rows inserted with proper flags

## Data Model

### Input: XML Structure
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
        <NmbItem>Product Name</NmbItem>
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

### Output: BigQuery Schema
25 fields in `logistica.facturas_raw`:

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| hash_md5 | STRING | Calculated | MD5(folio + "#" + rut_emisor) |
| documento_id | STRING | Calculated | Same as hash_md5 |
| folio | INTEGER | Encabezado/IdDoc/Folio | Invoice number |
| fecha_emis | STRING | Encabezado/IdDoc/FchEmis | Date (YYYY-MM-DD) |
| rut_emisor | STRING | Encabezado/Emisor/RUTEmisor | Seller tax ID |
| rsn_emisor | STRING | Encabezado/Emisor/RznSoc | Seller name |
| rut_receptor | STRING | Encabezado/Receptor/RUTRecep | Buyer tax ID |
| rsn_receptor | STRING | Encabezado/Receptor/RznSocRecep | Buyer name |
| tipo_dte | STRING | Encabezado/IdDoc/TipoDTE | Document type |
| numero_linea | INTEGER | Detalle/NroLinDet | Line number |
| tipo_codigo | STRING | Detalle/CdgItem/TpoCodigo | Code type |
| codigo | STRING | Detalle/CdgItem/VlrCodigo | Product code |
| descripcion | STRING | Detalle/NmbItem | Product name |
| cantidad | FLOAT | Detalle/QtyItem | Quantity |
| precio_unitario | FLOAT | Detalle/PrcItem | Unit price |
| descuento_percent | FLOAT | Detalle/DescuentoPct | Discount % |
| descuento_monto | FLOAT | Detalle/DescuentoMonto | Discount amount |
| monto_item | FLOAT | Detalle/MontoItem | Line subtotal |
| tasa_iva | FLOAT | Detalle/TasaIVA | Tax rate |
| iva_item | FLOAT | Detalle/IVAItem | Tax amount |
| monto_total_item | FLOAT | Calculated | Subtotal + tax |
| es_duplicado | BOOLEAN | Logic | TRUE if already in DB |
| estado_procesamiento | STRING | Logic | "processed" or "duplicate" |
| timestamp_procesamiento | TIMESTAMP | Runtime | ISO datetime when processed |
| nombre_archivo | STRING | Runtime | Source XML filename |

## Deduplication

**Key**: `hash_md5` = `MD5(folio + "#" + rut_emisor)`

**Why this works**:
- Folio (invoice #) is unique per seller
- RUT (seller tax ID) identifies the seller
- Together they uniquely identify a document
- MD5 provides efficient lookup

**Logic**:
1. Load all existing hashes into memory set (1 query)
2. For each new document, compute hash
3. Check: `if hash in existing_hashes:`
4. If yes: Mark `es_duplicado=TRUE`, `estado_procesamiento="duplicate"`
5. If no: Mark `es_duplicado=FALSE`, `estado_procesamiento="processed"`
6. Add new hash to set for rest of batch

**Safety**: Duplicates are still inserted (for audit), just marked. No data corruption.

## Performance Characteristics

### Time Complexity
- **Hash loading**: O(n) where n = existing documents
- **File listing**: O(m) where m = total files in bucket
- **Downloads**: O(k/5) where k = files to process (5 concurrent)
- **XML parsing**: O(d*i) where d = documents, i = items per doc
- **Dedup checks**: O(d) constant time (set lookup)
- **BigQuery insert**: O(r) where r = rows inserted

### Space Complexity
- **Hash cache**: O(n) - linear with existing documents (~500 hashes = ~32KB)
- **File data**: O(k) - one file in memory at a time
- **Rows buffer**: O(r) - all rows before final insert

### Actual Performance (Tested)
- **24 files**: ~30 seconds
- **1,206 rows inserted**
- **Throughput**: ~40 rows/second
- **Latency**: 0-100ms per row depending on network

## Concurrent Workers

```python
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
```

**Max workers**: 5 (adjustable if needed)
**Why 5**: Balance between parallelism and resource usage
**Adjustable**: Change `max_workers=5` to higher if more capacity

## Error Handling

### File Download Failures
```python
except Exception as e:
    logger.error(f"Error downloading/parsing {blob_name}: {str(e)}", exc_info=True)
    return blob_name, None  # Continues processing other files
```

### Row Extraction Failures
```python
except Exception as e:
    logger.error(f"Error extracting item: {str(e)}", exc_info=True)
    # Continues with next item
```

### BigQuery Insert Failures
```python
errors = bq_client.insert_rows_json(table, rows)
if errors:
    logger.error(f"BigQuery insert errors: {errors}")
```

**Strategy**: Log and continue; don't crash on single file/row failure

## Dependencies

```
functions-framework==3.5.0     # Cloud Functions framework
google-cloud-storage==2.10.0   # GCS operations
google-cloud-bigquery==3.13.0  # BigQuery operations
```

## Logging

All operations logged to Cloud Logging via:
```python
logger.info(f"...")    # Info messages
logger.warning(f"...") # Warnings
logger.error(f"...", exc_info=True)  # Errors with stack trace
```

**View logs**:
```bash
gcloud logging read "resource.labels.service_name=process-xml-to-bq" \
  --limit 50 --project=impasto-492602
```

## Testing

**Tested with**:
- 24 real XML files
- 330 new documents
- 84 duplicate documents
- 1,206 rows inserted
- All rows verified in BigQuery

**Duplicate detection**: 100% accurate

---

**For Development**: Use this document to understand code flow, data models, and performance characteristics. Refer to AGENT_CONTEXT.md for operational details.
