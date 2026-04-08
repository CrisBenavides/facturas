"""
Main entry point for the Facturas XML Processor
"""

import logging
import json
from config.settings import Settings
from src.utils import setup_logging
from src.scraper import XMLProcessor

logger = logging.getLogger(__name__)


def main():
    """Main execution function"""
    try:
        # Setup logging
        setup_logging(Settings.LOG_PATH, Settings.LOG_LEVEL)
        logger.info("Starting Facturas XML Processor")
        
        # Validate settings and create directories
        Settings.validate()
        logger.info(f"Data path: {Settings.DATA_PATH}")
        logger.info(f"Output path: {Settings.OUTPUT_PATH}")
        
        # Initialize XML processor
        processor = XMLProcessor(Settings.DATA_PATH)
        
        # Process all XML files
        result, input_filename = processor.process_all_files()
        
        if not result["SetDTE"]["DTE"]:
            logger.warning("No XML files were processed")
            return 1
        
        # Save results to JSON with same nomenclature as input
        output_filename = f"{input_filename}.json" if input_filename else "processed_documents.json"
        output_file = f"{Settings.OUTPUT_PATH}/{output_filename}"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to: {output_file}")
        logger.info(f"Successfully processed {len(result['SetDTE']['DTE'])} documents")
        
        return 0
        
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())
