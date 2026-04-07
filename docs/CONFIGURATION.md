# Configuration Guide

## Environment Setup

1. **Create `.env` file** from the template:
   ```bash
   copy .env.example .env
   ```

2. **Edit `.env` with your settings**:

## Required Settings

### SII Credentials
- `SII_RUT`: Your RUT number (e.g., "12.345.678-9")
- `SII_PASSWORD`: Your SII account password

### Paths
- `DOWNLOAD_PATH`: Directory for downloaded XLM files (default: `./data`)
- `LOG_PATH`: Directory for log files (default: `./logs`)

### Browser Settings
- `BROWSER_TYPE`: Browser to use - `chrome` or `firefox` (default: `chrome`)
- `HEADLESS`: Run browser in headless mode - `True` or `False` (default: `True`)

### Request Settings
- `REQUEST_TIMEOUT`: Request timeout in seconds (default: `30`)
- `RETRY_ATTEMPTS`: Number of retry attempts (default: `3`)

### Logging
- `LOG_LEVEL`: Logging level - `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (default: `INFO`)

## Example Configuration

```
SII_RUT=12.345.678-9
SII_PASSWORD=your_password_here
DOWNLOAD_PATH=./data
LOG_PATH=./logs
BROWSER_TYPE=chrome
HEADLESS=True
REQUEST_TIMEOUT=30
RETRY_ATTEMPTS=3
LOG_LEVEL=INFO
```

## Security Notes

- Never commit `.env` file to version control
- Keep credentials secure
- Use strong passwords
- Consider using environment-specific credentials
