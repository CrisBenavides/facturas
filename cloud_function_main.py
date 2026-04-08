"""
Cloud Function: Process XML files uploaded to Cloud Storage
Converts XML to JSON, checks for duplicates, and inserts into BigQuery
"""

import functions_framework
from google.cloud import storage, bigquery
from google.cloud.exceptions import NotFound
import json
import xml.etree.ElementTree as ET
import hashlib
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GCP Configuration
PROJECT_ID = "impasto-492602"
DATASET_ID = "logistica"
TABLE_ID = "facturas_raw"
BUCKET_NAME = "facturas-xml-uploads"


@functions_framework.http
def process_xml_to_bq(request):
    """
    HTTP Cloud Function for Cloud Storage events.
    Triggered via Pub/Sub when files are uploaded to Cloud Storage.
    """
    try:
        # Initialize clients (lazy loading to avoid startup errors)
        storage_client = storage.Client()
        bq_client = bigquery.Client()
        
        # Parse Cloud Event from request
        import base64
        envelope = request.get_json()
        if not envelope:
            return ("Bad Request: no Pub/Sub message received", 400)
        
        if not isinstance(envelope, dict) or "message" not in envelope:
            return ("Bad Request: invalid Pub/Sub message format", 400)
        
        pubsub_message = envelope["message"]
        
        # Decode the Pub/Sub message
        if isinstance(pubsub_message, dict) and "data" in pubsub_message:
            payload = json.loads(base64.b64decode(pubsub_message["data"]).decode())
        else:
            return ("Bad Request: missing message data", 400)
        
        bucket_name = payload.get("bucket")
        file_name = payload.get("name")
        
        if not bucket_name or not file_name:
            return ("Bad Request: missing bucket or file name", 400)
        
        logger.info(f"Processing file: {file_name} from bucket: {bucket_name}")
        
        # Download and parse XML file
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        xml_content = blob.download_as_string()
        
        # Parse XML
        root = ET.fromstring(xml_content)
        
        # Extract all documents
        rows_to_insert = []
        for dte in root.findall("DTE"):
            documento = dte.find("Documento")
            if documento is not None:
                row = extract_document_row(documento, file_name)
                if row:
                    # Check for duplicates
                    if not is_duplicate(row, bq_client):
                        row["processing_status"] = "processed"
                        rows_to_insert.append(row)
                    else:
                        row["processing_status"] = "duplicate"
                        row["is_duplicate"] = True
                        rows_to_insert.append(row)
        
        # Insert into BigQuery
        if rows_to_insert:
            insert_rows_to_bigquery(rows_to_insert, bq_client)
            logger.info(f"Inserted {len(rows_to_insert)} rows into BigQuery")
        
        return ("OK", 200)
        
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}", exc_info=True)
        return (f"Error: {str(e)}", 500)


def extract_document_row(documento: ET.Element, filename: str) -> dict:
    """
    Extract document data and convert to BigQuery row format.
    
    Args:
        documento: The Documento XML element
        filename: Source filename
        
    Returns:
        Dictionary representing a BigQuery row
    """
    try:
        encabezado = documento.find("Encabezado")
        if encabezado is None:
            return None
            
        iddoc = encabezado.find("IdDoc")
        emisor = encabezado.find("Emisor")
        receptor = encabezado.find("Receptor")
        totales = encabezado.find("Totales")
        
        # Extract values
        tipo_dte = iddoc.findtext("TipoDTE") if iddoc is not None else None
        folio = iddoc.findtext("Folio") if iddoc is not None else None
        fecha_emis = iddoc.findtext("FchEmis") if iddoc is not None else None
        rut_emisor = emisor.findtext("RUTEmisor") if emisor is not None else None
        rsn_emisor = emisor.findtext("RznSoc") if emisor is not None else None
        rut_receptor = receptor.findtext("RUTRecep") if receptor is not None else None
        rsn_receptor = receptor.findtext("RznSocRecep") if receptor is not None else None
        mnt_neto = totales.findtext("MntNeto") if totales is not None else None
        iva = totales.findtext("IVA") if totales is not None else None
        mnt_total = totales.findtext("MntTotal") if totales is not None else None
        
        # Extract line items
        detalles = []
        for detalle in documento.findall("Detalle"):
            detalle_dict = element_to_dict(detalle)
            detalles.append(detalle_dict)
        
        # Create hash for deduplication
        hash_key = f"{folio}#{rut_emisor}"
        hash_documento = hashlib.md5(hash_key.encode()).hexdigest()
        
        # Build row
        row = {
            "file_timestamp": datetime.utcnow().isoformat(),
            "source_filename": filename,
            "tipo_dte": tipo_dte,
            "folio": folio,
            "fecha_emis": fecha_emis,
            "rut_emisor": rut_emisor,
            "rsn_emisor": rsn_emisor,
            "rut_receptor": rut_receptor,
            "rsn_receptor": rsn_receptor,
            "mnt_neto": int(mnt_neto) if mnt_neto else None,
            "iva": int(iva) if iva else None,
            "mnt_total": int(mnt_total) if mnt_total else None,
            "detalle_json": json.dumps(detalles),
            "documento_json": json.dumps(element_to_dict(documento)),
            "hash_documento": hash_documento,
            "is_duplicate": False,
        }
        
        return row
        
    except Exception as e:
        logger.error(f"Error extracting document: {str(e)}", exc_info=True)
        return None


def is_duplicate(row: dict, bq_client: bigquery.Client) -> bool:
    """
    Check if a document already exists in BigQuery using hash.
    
    Args:
        row: The row to check
        bq_client: BigQuery client instance
        
    Returns:
        True if duplicate exists, False otherwise
    """
    try:
        query = f"""
        SELECT COUNT(*) as count 
        FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`
        WHERE hash_documento = @hash
        AND is_duplicate = FALSE
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("hash", "STRING", row["hash_documento"]),
            ]
        )
        
        query_job = bq_client.query(query, job_config=job_config)
        results = query_job.result()
        
        for result in results:
            return result.count > 0
            
        return False
        
    except Exception as e:
        logger.error(f"Error checking duplicates: {str(e)}", exc_info=True)
        return False


def insert_rows_to_bigquery(rows: list, bq_client: bigquery.Client) -> None:
    """
    Insert rows into BigQuery table.
    
    Args:
        rows: List of row dictionaries to insert
        bq_client: BigQuery client instance
    """
    try:
        table = bq_client.get_table(f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}")
        errors = bq_client.insert_rows_json(table, rows)
        
        if errors:
            logger.error(f"BigQuery insert errors: {errors}")
            raise Exception(f"Failed to insert rows: {errors}")
        else:
            logger.info(f"Successfully inserted {len(rows)} rows")
            
    except Exception as e:
        logger.error(f"Error inserting rows: {str(e)}", exc_info=True)
        raise


def element_to_dict(element: ET.Element) -> dict:
    """
    Convert XML element to dictionary recursively.
    
    Args:
        element: XML element
        
    Returns:
        Dictionary representation
    """
    result = {}
    for child in element:
        if len(child) == 0:
            # Leaf node
            result[child.tag] = child.text
        else:
            # Has children - recurse
            result[child.tag] = element_to_dict(child)
    return result
