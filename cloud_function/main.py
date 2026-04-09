import functions_framework
import json
import base64
import logging
import hashlib
from datetime import datetime
import xml.etree.ElementTree as ET
import concurrent.futures
from functools import partial
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = "impasto-492602"
DATASET_ID = "logistica"
TABLE_ID = "facturas_raw"


def element_to_dict(element):
    """Convert XML element to dictionary recursively"""
    result = {}
    for child in element:
        if len(child) == 0:
            result[child.tag] = child.text
        else:
            result[child.tag] = element_to_dict(child)
    return result



def extract_item_rows(documento, filename):
    """Extract item-level rows from Documento for BigQuery"""
    try:
        logger.info(f"extract_item_rows called with filename: {filename}")
        encabezado = documento.find("Encabezado")
        if encabezado is None:
            logger.error("Encabezado not found")
            return []

        iddoc = encabezado.find("IdDoc")
        emisor = encabezado.find("Emisor")
        receptor = encabezado.find("Receptor")
        logger.info(f"Found Encabezado sub-elements: IdDoc={iddoc is not None}, Emisor={emisor is not None}, Receptor={receptor is not None}")

        tipo_dte = iddoc.findtext("TipoDTE") if iddoc is not None else None
        folio = iddoc.findtext("Folio") if iddoc is not None else None
        fecha_emis = iddoc.findtext("FchEmis") if iddoc is not None else None
        rut_emisor = emisor.findtext("RUTEmisor") if emisor is not None else None
        rsn_emisor = emisor.findtext("RznSoc") if emisor is not None else None
        rut_receptor = receptor.findtext("RUTRecep") if receptor is not None else None
        rsn_receptor = receptor.findtext("RznSocRecep") if receptor is not None else None
        logger.info(f"Extracted header: folio={folio}, rut_emisor={rut_emisor}, tipo_dte={tipo_dte}")

        hash_key = f"{folio}#{rut_emisor}"
        hash_documento = hashlib.md5(hash_key.encode()).hexdigest()
        logger.info(f"Generated hash_documento: {hash_documento}")

        detalles = documento.findall("Detalle")
        logger.info(f"Found {len(detalles)} <Detalle> items in Documento (folio={folio})")
        rows = []
        for detalle_idx, detalle in enumerate(detalles):
            try:
                nrolin = detalle.findtext("NroLinDet")
                tipo_codigo = None
                codigo = None
                codigos = detalle.findall("CdgItem")
                if codigos:
                    # Take first code if multiple
                    tipo_codigo = codigos[0].findtext("TpoCodigo")
                    codigo = codigos[0].findtext("VlrCodigo")
                descripcion = detalle.findtext("NmbItem")
                cantidad = detalle.findtext("QtyItem") or detalle.findtext("Qty") or detalle.findtext("QtyDet") or detalle.findtext("Qty") or detalle.findtext("Qty")
                if cantidad is None:
                    cantidad = detalle.findtext("Qty")
                precio_unitario = detalle.findtext("PrcItem")
                descuento_percent = detalle.findtext("DescuentoPct")
                descuento_monto = detalle.findtext("DescuentoMonto")
                monto_item = detalle.findtext("MontoItem")
                tasa_iva = detalle.findtext("TasaIVA")
                iva_item = detalle.findtext("IVAItem")
                monto_total_item = None
                try:
                    if monto_item and iva_item:
                        monto_total_item = float(monto_item) + float(iva_item)
                    elif monto_item:
                        monto_total_item = float(monto_item)
                except:
                    monto_total_item = None

                row = {
                    "documento_id": hash_documento,
                    "folio": int(folio) if folio else None,
                    "fecha_emis": fecha_emis,
                    "rut_emisor": rut_emisor,
                    "rsn_emisor": rsn_emisor,
                    "rut_receptor": rut_receptor,
                    "rsn_receptor": rsn_receptor,
                    "tipo_dte": tipo_dte,
                    "numero_linea": int(nrolin) if nrolin else None,
                    "tipo_codigo": tipo_codigo,
                    "codigo": codigo,
                    "descripcion": descripcion,
                    "cantidad": float(cantidad) if cantidad else None,
                    "precio_unitario": float(precio_unitario) if precio_unitario else None,
                    "descuento_percent": float(descuento_percent) if descuento_percent else None,
                    "descuento_monto": float(descuento_monto) if descuento_monto else None,
                    "monto_item": float(monto_item) if monto_item else None,
                    "tasa_iva": float(tasa_iva) if tasa_iva else None,
                    "iva_item": float(iva_item) if iva_item else None,
                    "monto_total_item": float(monto_total_item) if monto_total_item else None,
                    "es_duplicado": False,
                    "estado_procesamiento": None,  # to be set later
                    "hash_md5": hash_documento,
                    "timestamp_procesamiento": datetime.utcnow().isoformat(),
                    "nombre_archivo": filename,
                }
                rows.append(row)
            except Exception as e:
                logger.error(f"Error extracting item: {str(e)}", exc_info=True)
        return rows
    except Exception as e:
        logger.error(f"Error extracting items: {str(e)}", exc_info=True)
        return []


def insert_rows_to_bigquery(rows: list, bq_client) -> None:
    """Insert rows into BigQuery table"""
    try:
        if not rows:
            return
            
        table = bq_client.get_table(f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}")
        errors = bq_client.insert_rows_json(table, rows)
        
        if errors:
            logger.error(f"BigQuery insert errors: {errors}")
        else:
            logger.info(f"Successfully inserted {len(rows)} rows")
            
    except Exception as e:
        logger.error(f"Error inserting rows: {str(e)}")


def download_and_parse_xml(blob_name, storage_client, bucket_name):
    """Download and parse a single XML file - for concurrent processing"""
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        xml_content = blob.download_as_string()
        logger.info(f"Downloaded {blob_name} ({len(xml_content)} bytes)")
        root = ET.fromstring(xml_content)
        return blob_name, root
    except Exception as e:
        logger.error(f"Error downloading/parsing {blob_name}: {str(e)}", exc_info=True)
        return blob_name, None


@functions_framework.http
def process_xml_to_bq(request):
    """HTTP endpoint - batch process multiple XML files efficiently"""
    try:
        logger.info("=== BATCH PROCESSING STARTED ===")
        
        # Parse request
        try:
            data = request.get_json()
            file_pattern = data.get("name", "DTE_Recibidos") if data else "DTE_Recibidos"
        except:
            file_pattern = "DTE_Recibidos"
        
        bucket_name = "facturas-xml-uploads"
        
        # Lazy load clients
        from google.cloud import storage, bigquery
        
        storage_client = storage.Client()
        bq_client = bigquery.Client()
        logger.info("Clients initialized")
        
        # ✓ OPTIMIZATION 1: Load ALL existing document hashes ONCE into memory
        logger.info("Loading existing document hashes from BigQuery (ONE query)...")
        query = f"""
        SELECT DISTINCT hash_documento 
        FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`
        WHERE hash_documento IS NOT NULL
        """
        
        existing_hashes = set()
        try:
            query_job = bq_client.query(query)
            for row in query_job.result():
                existing_hashes.add(row["hash_documento"])
            logger.info(f"Loaded {len(existing_hashes)} existing document hashes into memory")
        except Exception as e:
            logger.warning(f"Error loading existing hashes: {str(e)}. Continuing with empty cache.")
            existing_hashes = set()
        
        # Get files to process
        logger.info(f"Listing files matching pattern: {file_pattern}")
        bucket = storage_client.bucket(bucket_name)
        
        # Handle wildcard patterns
        if "*" in file_pattern:
            pattern_regex = file_pattern.replace("*", ".*")
        else:
            pattern_regex = f".*{file_pattern}.*"
        
        # List all matching XML files
        all_blobs = list(bucket.list_blobs())
        matching_blobs = [
            blob for blob in all_blobs 
            if re.match(pattern_regex, blob.name) and blob.name.endswith('.xml')
        ]
        
        logger.info(f"Found {len(matching_blobs)} XML files matching pattern: {file_pattern}")
        
        if not matching_blobs:
            logger.warning(f"No XML files found matching pattern: {file_pattern}")
            return ("No files found", 400)
        
        # ✓ OPTIMIZATION 2: Download and parse files concurrently (max 5 workers)
        logger.info(f"Downloading {len(matching_blobs)} files concurrently (5 workers)...")
        file_data = []
        
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                results = executor.map(
                    partial(download_and_parse_xml, storage_client=storage_client, bucket_name=bucket_name),
                    [blob.name for blob in matching_blobs]
                )
                file_data = [(name, root) for name, root in results if root is not None]
        except Exception as e:
            logger.error(f"Error during concurrent download: {str(e)}", exc_info=True)
            file_data = []
        
        logger.info(f"Successfully downloaded and parsed {len(file_data)} files")
        
        # ✓ OPTIMIZATION 3: Process all files, checking hashes against cached set (instant lookup)
        total_rows_inserted = 0
        processed_files = 0
        duplicate_files = 0
        processed_documents = 0
        duplicate_documents = 0
        
        for file_name, root in file_data:
            try:
                rows_to_insert = []
                dtes = root.findall("DTE")
                logger.info(f"Processing {file_name}: {len(dtes)} DTE elements")
                
                for dte in dtes:
                    documento = dte.find("Documento")
                    if documento is not None:
                        item_rows = extract_item_rows(documento, file_name)
                        
                        if not item_rows:
                            continue
                        
                        # ✓ CHECK AGAINST CACHED HASHES (instant in-memory lookup)
                        dedup_row = item_rows[0]
                        doc_hash = dedup_row["hash_md5"]
                        is_dup = doc_hash in existing_hashes
                        
                        if is_dup:
                            logger.info(f"  → Duplicate document detected: folio={dedup_row['folio']}")
                            duplicate_documents += 1
                            for row in item_rows:
                                row["estado_procesamiento"] = "duplicate"
                                row["es_duplicado"] = True
                                rows_to_insert.append(row)
                        else:
                            logger.info(f"  → New document: folio={dedup_row['folio']}")
                            processed_documents += 1
                            # Add to cache for subsequent checks in this batch
                            existing_hashes.add(doc_hash)
                            for row in item_rows:
                                row["estado_procesamiento"] = "processed"
                                row["es_duplicado"] = False
                                rows_to_insert.append(row)
                
                # Batch insert all rows from this file
                if rows_to_insert:
                    insert_rows_to_bigquery(rows_to_insert, bq_client)
                    total_rows_inserted += len(rows_to_insert)
                    processed_files += 1
                    logger.info(f"✓ {file_name}: {len(rows_to_insert)} rows inserted")
                else:
                    logger.info(f"⚠ {file_name}: no rows to insert")
            
            except Exception as e:
                logger.error(f"Error processing {file_name}: {str(e)}", exc_info=True)
                continue
        
        logger.info("=== BATCH PROCESSING COMPLETED ===")
        summary = (
            f"Processed {processed_files} files | "
            f"{processed_documents} new documents | "
            f"{duplicate_documents} duplicate documents | "
            f"{total_rows_inserted} rows inserted"
        )
        logger.info(summary)
        return (summary, 200)
        
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return (f"Error: {str(e)}", 500)
