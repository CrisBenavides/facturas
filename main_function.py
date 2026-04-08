"""
Simplified Cloud Function for Cloud Storage events
"""

import functions_framework
from google.cloud import storage, bigquery
import json
import xml.etree.ElementTree as ET
import hashlib
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = "impasto-492602"
DATASET_ID = "logistica"
TABLE_ID = "facturas_raw"

storage_client = storage.Client()
bq_client = bigquery.Client()


def element_to_dict(element):
    """Convert XML element to dict"""
    result = {}
    for child in element:
        if len(child) == 0:
            result[child.tag] = child.text
        else:
            result[child.tag] = element_to_dict(child)
    return result


@functions_framework.cloud_event
def main(cloud_event):
    """Cloud Storage trigger"""
    try:
        data = cloud_event.data
        bucket_name = data["bucket"]
        file_name = data["name"]
        
        logger.info(f"Processing: {file_name}")
        
        # Download
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        xml_content = blob.download_as_string()
        
        # Parse
        root = ET.fromstring(xml_content)
        
        rows = []
        for dte in root.findall("DTE"):
            doc = dte.find("Documento")
            if doc:
                encab = doc.find("Encabezado")
                iddoc = encab.find("IdDoc")
                emisor = encab.find("Emisor")
                receptor = encab.find("Receptor")
                totales = encab.find("Totales")
                
                folio = iddoc.findtext("Folio")
                rut_emisor = emisor.findtext("RUTEmisor")
                
                hash_val = hashlib.md5(f"{folio}#{rut_emisor}".encode()).hexdigest()
                
                row = {
                    "folio": folio,
                    "rut_emisor": rut_emisor,
                    "nombre_emisor": emisor.findtext("RznSoc"),
                    "rut_receptor": receptor.findtext("RUTRecep"),
                    "nombre_receptor": receptor.findtext("RznSocRecep"),
                    "mnt_total": int(totales.findtext("MntTotal") or 0),
                    "hash_documento": hash_val,
                    "is_duplicate": False,
                    "processing_status": "processed",
                    "source_filename": file_name,
                    "documento_json": json.dumps(element_to_dict(doc)),
                    "timestamp_processing": datetime.utcnow().isoformat(),
                }
                rows.append(row)
        
        # Insert
        if rows:
            table = bq_client.get_table(f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}")
            bq_client.insert_rows_json(table, rows)
            logger.info(f"Inserted {len(rows)} rows")
        
        return "OK", 200
        
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return f"Error: {str(e)}", 500
