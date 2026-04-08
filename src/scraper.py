"""
XML processor module for SII documents
"""

import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class XMLProcessor:
    """Processor for SII XML documents"""

    def __init__(self, data_path: str):
        """
        Initialize the XML processor
        
        Args:
            data_path: Path to the data directory containing XML files
        """
        self.data_path = Path(data_path)
        self.documents = []

    def load_xml_files(self) -> List[Path]:
        """
        Load all XML files from the data directory
        
        Returns:
            List of Path objects for XML files found
        """
        try:
            xml_files = list(self.data_path.glob("*.xml"))
            logger.info(f"Found {len(xml_files)} XML files in {self.data_path}")
            return xml_files
        except Exception as e:
            logger.error(f"Error loading XML files: {str(e)}")
            return []

    def parse_xml(self, file_path: Path) -> Optional[ET.Element]:
        """
        Parse a single XML file
        
        Args:
            file_path: Path to the XML file
            
        Returns:
            ElementTree root element or None if parsing fails
        """
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            logger.info(f"Successfully parsed: {file_path.name}")
            return root
        except Exception as e:
            logger.error(f"Error parsing {file_path.name}: {str(e)}")
            return None

    def extract_document_info(self, documento: ET.Element) -> Dict:
        """
        Extract document information from a Documento element
        
        Args:
            documento: The Documento element to extract from
            
        Returns:
            Dictionary with extracted document information
        """
        try:
            if documento is None:
                logger.warning("No Documento element provided")
                return {}

            # Extract header information
            encabezado = documento.find("Encabezado")
            if encabezado is None:
                return {}

            iddoc = encabezado.find("IdDoc")
            emisor = encabezado.find("Emisor")
            receptor = encabezado.find("Receptor")
            totales = encabezado.find("Totales")

            doc_info = {
                "tipo_dte": iddoc.findtext("TipoDTE") if iddoc is not None else None,
                "folio": iddoc.findtext("Folio") if iddoc is not None else None,
                "fecha_emis": iddoc.findtext("FchEmis") if iddoc is not None else None,
                "rut_emisor": emisor.findtext("RUTEmisor") if emisor is not None else None,
                "rsn_emisor": emisor.findtext("RznSoc") if emisor is not None else None,
                "rut_receptor": receptor.findtext("RUTRecep") if receptor is not None else None,
                "rsn_receptor": receptor.findtext("RznSocRecep") if receptor is not None else None,
                "mnt_neto": totales.findtext("MntNeto") if totales is not None else None,
                "iva": totales.findtext("IVA") if totales is not None else None,
                "mnt_total": totales.findtext("MntTotal") if totales is not None else None,
            }

            return doc_info
        except Exception as e:
            logger.error(f"Error extracting document info: {str(e)}")
            return {}

    def extract_details(self, documento: ET.Element) -> List[Dict]:
        """
        Extract line item details from a Documento element
        
        Args:
            documento: The Documento element to extract from
            
        Returns:
            List of detail dictionaries
        """
        try:
            if documento is None:
                return []

            details = []
            for detalle in documento.findall("Detalle"):
                detail_info = {
                    "nro_lin": detalle.findtext("NroLinDet"),
                    "item": detalle.findtext("NmbItem"),
                    "cantidad": detalle.findtext("QtyItem"),
                    "unidad": detalle.findtext("UnmdItem"),
                    "precio": detalle.findtext("PrcItem"),
                    "monto": detalle.findtext("MontoItem"),
                }
                details.append(detail_info)

            logger.info(f"Extracted {len(details)} line items")
            return details
        except Exception as e:
            logger.error(f"Error extracting details: {str(e)}")
            return []

    def process_all_files(self) -> tuple[Dict, str]:
        """
        Process all XML files in the data directory
        
        Returns:
            Tuple of (processed data dict, first input filename)
        """
        xml_files = self.load_xml_files()
        dte_list = []
        first_filename = None

        for file_path in xml_files:
            if first_filename is None:
                first_filename = file_path.stem  # Get filename without extension
                
            xml_root = self.parse_xml(file_path)
            if xml_root is not None:
                # Find all DTE elements (each contains one Documento)
                for dte in xml_root.findall("DTE"):
                    documento = dte.find("Documento")
                    if documento is not None:
                        encabezado = documento.find("Encabezado")
                        if encabezado is not None:
                            iddoc = encabezado.find("IdDoc")
                            emisor = encabezado.find("Emisor")
                            receptor = encabezado.find("Receptor")
                            totales = encabezado.find("Totales")
                            
                            # Build structured DTE object
                            dte_obj = {
                                "Documento": {
                                    "Encabezado": {
                                        "IdDoc": self._element_to_dict(iddoc) if iddoc is not None else {},
                                        "Emisor": self._element_to_dict(emisor) if emisor is not None else {},
                                        "Receptor": self._element_to_dict(receptor) if receptor is not None else {},
                                        "Totales": self._element_to_dict(totales) if totales is not None else {},
                                    },
                                    "Detalle": [self._element_to_dict(d) for d in documento.findall("Detalle")]
                                }
                            }
                            dte_list.append(dte_obj)

        result = {"SetDTE": {"DTE": dte_list}}
        logger.info(f"Processed {len(dte_list)} documents")
        return result, first_filename


    @staticmethod
    def _element_to_dict(element: ET.Element) -> Dict:
        """
        Convert an XML element and its children to a dictionary
        
        Args:
            element: XML element to convert
            
        Returns:
            Dictionary representation of the element
        """
        result = {}
        for child in element:
            if len(child) == 0:
                # Leaf node
                result[child.tag] = child.text
            else:
                # Has children - recurse
                result[child.tag] = XMLProcessor._element_to_dict(child)
        return result

