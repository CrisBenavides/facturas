import functions_framework

@functions_framework.http
def process_xml_to_bq(request):
    """Minimal test function"""
    return "OK", 200
