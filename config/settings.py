"""
Configuration settings for the XML processor
"""

import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings"""

    # Paths
    DATA_PATH = os.getenv("DATA_PATH", "./data")
    OUTPUT_PATH = os.getenv("OUTPUT_PATH", "./output")
    LOG_PATH = os.getenv("LOG_PATH", "./logs")
    
    # File extensions
    ALLOWED_EXTENSIONS = [".xml"]
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls) -> bool:
        """
        Validate required settings and create directories if needed
        
        Returns:
            bool: True if all required settings are valid
        """
        Path(cls.DATA_PATH).mkdir(parents=True, exist_ok=True)
        Path(cls.OUTPUT_PATH).mkdir(parents=True, exist_ok=True)
        Path(cls.LOG_PATH).mkdir(parents=True, exist_ok=True)
        return True
        return True

    @classmethod
    def to_dict(cls) -> dict:
        """
        Convert settings to dictionary
        
        Returns:
            Dictionary of settings
        """
        return {
            "sii_rut": cls.SII_RUT,
            "download_path": cls.DOWNLOAD_PATH,
            "log_path": cls.LOG_PATH,
            "browser_type": cls.BROWSER_TYPE,
            "headless": cls.HEADLESS,
            "request_timeout": cls.REQUEST_TIMEOUT,
            "retry_attempts": cls.RETRY_ATTEMPTS,
            "log_level": cls.LOG_LEVEL,
        }


# Create singleton instance
settings = Settings()
