"""
Utility functions for the scraper
"""

import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def setup_logging(log_path: str = "./logs", level: str = "INFO") -> None:
    """
    Configure logging for the application
    
    Args:
        log_path: Path for log files
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    if not os.path.exists(log_path):
        os.makedirs(log_path)

    log_filename = f"{log_path}/facturas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )
    
    logger.info(f"Logging configured. Log file: {log_filename}")


def format_rut(rut: str) -> str:
    """
    Format Chilean RUT number
    
    Args:
        rut: RUT number (with or without formatting)
        
    Returns:
        Formatted RUT with dash
    """
    rut = rut.replace(".", "").replace("-", "").upper()
    if len(rut) >= 2:
        return f"{rut[:-1]}-{rut[-1]}"
    return rut


def validate_rut(rut: str) -> bool:
    """
    Validate Chilean RUT number
    
    Args:
        rut: RUT number
        
    Returns:
        bool: True if valid RUT format
    """
    rut = rut.replace(".", "").replace("-", "").upper()
    
    if not rut or len(rut) < 2:
        return False
    
    try:
        rut_digits = rut[:-1]
        rut_dv = rut[-1]
        
        if not rut_digits.isdigit():
            return False
            
        return True
    except Exception:
        return False


def ensure_directory(path: str) -> None:
    """
    Ensure directory exists, create if needed
    
    Args:
        path: Directory path
    """
    if not os.path.exists(path):
        os.makedirs(path)
        logger.info(f"Created directory: {path}")
