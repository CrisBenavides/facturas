"""
File download handler for SII documents
"""

import logging
import os
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DocumentDownloader:
    """Handle downloading SII documents"""

    def __init__(self, download_path: str = "./data"):
        """
        Initialize downloader
        
        Args:
            download_path: Path where documents will be saved
        """
        self.download_path = download_path
        self._ensure_download_path()

    def _ensure_download_path(self):
        """Ensure download path exists"""
        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)
            logger.info(f"Created download directory: {self.download_path}")

    def download(self, url: str, filename: str, headers: Optional[dict] = None) -> bool:
        """
        Download a file from URL
        
        Args:
            url: URL to download from
            filename: Name for the saved file
            headers: Optional HTTP headers
            
        Returns:
            bool: True if download successful
        """
        try:
            logger.info(f"Downloading: {filename}")
            # TODO: Implement download logic
            filepath = os.path.join(self.download_path, filename)
            logger.info(f"Saved to: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Download failed for {filename}: {str(e)}")
            return False

    def get_filename_with_timestamp(self, base_name: str) -> str:
        """
        Generate filename with timestamp
        
        Args:
            base_name: Base filename
            
        Returns:
            Filename with timestamp
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(base_name)
        return f"{name}_{timestamp}{ext}"
