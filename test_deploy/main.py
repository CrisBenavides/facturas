import functions_framework
import json
import base64
import logging
import hashlib
from datetime import datetime
import xml.etree.ElementTree as ET

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


def is_duplicate(row: dict, bq_client) -> bool:
    """Check if document already exists in BigQuery"""
    try:
        query = f"""
        SELECT COUNT(*) as count 
        FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`
        WHERE hash_documento = @hash
        AND is_duplicate = FALSE
        """
        
        from google.cloud import bigquery
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("hash", "STRING", row["hash_documento"]),
            ]
        )
        
        query_job = bq_client.query(query, job_config=job_config)
        results = query_job.result()
        
        for result in results:
            if result["count"] > 0:
                logger.info(f"Duplicate found: {row['folio']}")
                return True
        
        return False
    except Exception as e:
        logger.error(f"Error checking duplicates: {str(e)}")
        return False


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


@functions_framework.http
def process_xml_to_bq(request):
    """HTTP endpoint - manually trigger after uploading XML to bucket"""
    try:
        logger.info("=== FUNCTION CALLED ===")
        
        # Parse request to get filename (or use latest in bucket)
        try:
            data = request.get_json()
            file_name = data.get("name") if data else None
        except:
            file_name = None
        
        bucket_name = "facturas-xml-uploads"
        
        logger.info(f"Processing: {file_name} from {bucket_name}")
        
        # Lazy load clients
        from google.cloud import storage, bigquery
        
        storage_client = storage.Client()
        bq_client = bigquery.Client()
        logger.info("Clients initialized")
        
        # If no filename provided, get the most recently uploaded file
        if not file_name:
            logger.info("No filename in request, getting latest XML file from bucket...")
            bucket = storage_client.bucket(bucket_name)
            blobs = list(bucket.list_blobs(prefix="DTE_Recibidos"))
            if blobs:
                # Get most recent by updated time
                latest_blob = max(blobs, key=lambda x: x.updated)
                file_name = latest_blob.name
                logger.info(f"Found latest file: {file_name}")
            else:
                logger.error("No XML files found in bucket")
                return ("No files found", 400)
        
        # Download XML
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        xml_content = blob.download_as_string()
        
        logger.info(f"Downloaded {len(xml_content)} bytes from {bucket_name}/{file_name}")
        
        # Parse XML
        root = ET.fromstring(xml_content)
        logger.info(f"Parsed XML root: {root.tag}")
        
        # Extract all documents
        rows_to_insert = []
        dtes = root.findall("DTE")
        logger.info(f"Found {len(dtes)} DTE elements")
        
        for dte_idx, dte in enumerate(dtes):
            logger.info(f"Processing DTE #{dte_idx+1}")
            documento = dte.find("Documento")
            if documento is not None:
                logger.info(f"Found Documento element")
                # Extract item-level rows
                item_rows = extract_item_rows(documento, file_name)
                logger.info(f"extract_item_rows returned {len(item_rows)} rows")
                
                if not item_rows:
                    logger.info("No item rows, skipping")
                    continue
                
                # Check for duplicates at document level
                dedup_row = item_rows[0]
                if not is_duplicate({"hash_documento": dedup_row["hash_md5"]}, bq_client):
                    logger.info(f"Not a duplicate, adding {len(item_rows)} rows (status: processed)")
                    for row in item_rows:
                        row["estado_procesamiento"] = "processed"
                        row["es_duplicado"] = False
                        rows_to_insert.append(row)
                else:
                    logger.info(f"Is a duplicate, adding {len(item_rows)} rows (status: duplicate)")
                    for row in item_rows:
                        row["estado_procesamiento"] = "duplicate"
                        row["es_duplicado"] = True
                        rows_to_insert.append(row)
            else:
                logger.warning("No Documento element found in DTE")
        
        logger.info(f"Total rows to insert: {len(rows_to_insert)}")
        
        # Insert into BigQuery
        if rows_to_insert:
            logger.info(f"Calling insert_rows_to_bigquery with {len(rows_to_insert)} rows")
            insert_rows_to_bigquery(rows_to_insert, bq_client)
            logger.info("=== FUNCTION COMPLETED SUCCESSFULLY ===")
            return (f"Processed {len(rows_to_insert)} rows", 200)
        else:
            logger.warning("No rows to insert")
            return ("No rows to insert", 200)
        
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return (f"Error: {str(e)}", 500)
