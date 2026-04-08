#!/bin/bash
# process_upload.sh - Trigger processing of uploaded XML files
# Usage: ./process_upload.sh [filename]

FUNCTION_URL="https://us-central1-impasto-492602.cloudfunctions.net/process_xml_to_bq"

if [ -z "$1" ]; then
    echo "Processing latest XML file in bucket..."
    curl -X POST "$FUNCTION_URL" \
      -H "Content-Type: application/json" \
      -d '{}'
else
    echo "Processing: $1"
    curl -X POST "$FUNCTION_URL" \
      -H "Content-Type: application/json" \
      -d "{\"name\":\"$1\"}"
fi

echo ""
echo "Waiting for processing..."
sleep 3

echo "Checking BigQuery for new rows..."
bq --project_id=impasto-492602 query --use_legacy_sql=false \
  "SELECT COUNT(*) as total_rows, COUNT(DISTINCT folio) as invoices FROM logistica.facturas_raw"
