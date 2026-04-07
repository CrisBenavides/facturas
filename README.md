# Facturas SII Scraper

Web scraper for downloading documents in XLM format from SII (Servicio de Impuestos Internos) of Chile.

## Project Structure

```
facturas/
├── src/                 # Source code
│   ├── __init__.py
│   ├── scraper.py       # Main scraper logic
│   ├── auth.py          # Authentication module
│   ├── downloader.py    # File download handler
│   └── utils.py         # Utility functions
├── config/              # Configuration files
│   └── settings.py      # Configuration settings
├── data/                # Downloaded files (XLM documents)
├── logs/                # Application logs
├── tests/               # Unit tests
├── docs/                # Documentation
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variables template
├── .gitignore           # Git ignore rules
└── main.py              # Entry point
```

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables:
   ```bash
   copy .env.example .env
   # Edit .env with your settings
   ```

## Usage

```bash
python main.py
```

## Configuration

See [Configuration Guide](docs/CONFIGURATION.md) for detailed setup instructions.

## Notes

- This tool is designed to interact with the SII (Chilean Tax Authority) systems
- Ensure compliance with SII terms of service when using this scraper
- All downloaded documents should be handled according to local regulations

## License

MIT License
