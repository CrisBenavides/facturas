"""
Configuration settings for the scraper
"""

import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings"""

    # SII Credentials
    SII_RUT = os.getenv("SII_RUT", "")
    SII_PASSWORD = os.getenv("SII_PASSWORD", "")

    # Paths
    DOWNLOAD_PATH = os.getenv("DOWNLOAD_PATH", "./data")
    LOG_PATH = os.getenv("LOG_PATH", "./logs")

    # Browser Settings
    BROWSER_TYPE = os.getenv("BROWSER_TYPE", "chrome")
    HEADLESS = os.getenv("HEADLESS", "True").lower() == "true"

    # Request Settings
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
    RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", "3"))

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # SII URLs (adjust as needed)
    SII_BASE_URL = "https://www.sii.cl"
    SII_LOGIN_URL = f"{SII_BASE_URL}/portales/login-ciudadano"

    @classmethod
    def validate(cls) -> bool:
        """
        Validate required settings
        
        Returns:
            bool: True if all required settings are valid
        """
        if not cls.SII_RUT or not cls.SII_PASSWORD:
            raise ValueError(
                "SII_RUT and SII_PASSWORD must be set in .env file"
            )
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
