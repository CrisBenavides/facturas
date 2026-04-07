"""
Main entry point for the Facturas SII Scraper
"""

import logging
from config.settings import settings
from src.utils import setup_logging
from src.scraper import SIIScraper

logger = logging.getLogger(__name__)


def main():
    """Main execution function"""
    try:
        # Setup logging
        setup_logging(settings.LOG_PATH, settings.LOG_LEVEL)
        logger.info("Starting Facturas SII Scraper")
        
        # Validate settings
        settings.validate()
        
        # Initialize scraper
        scraper = SIIScraper(settings.to_dict())
        
        # Authenticate
        if not scraper.authenticate():
            logger.error("Failed to authenticate with SII")
            return 1
        
        # TODO: Add main logic here
        logger.info("Scraper initialized successfully")
        
        # Cleanup
        scraper.close()
        logger.info("Scraper completed successfully")
        
        return 0
        
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())
