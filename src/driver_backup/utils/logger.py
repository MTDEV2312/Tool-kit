import logging
from pathlib import Path

# Create a module-level logger
logger = logging.getLogger("driver_backup")


def setup_logger(log_level: str = "INFO", enable_console: bool = False) -> Path:
    """Configure logging to file (and optionally console) and return log file path."""
    log_dir = Path.home() / ".driver_backup"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "driver_backup.log"

    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Clear existing handlers to avoid duplicates on re-entry
    logger.handlers.clear()

    # Format setup
    formatter = logging.Formatter(
        "%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
    )

    # File Handler setup
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(numeric_level)
    logger.addHandler(file_handler)

    if enable_console:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(numeric_level)
        logger.addHandler(stream_handler)

    return log_file


def get_log_file_path() -> Path:
    """Return the absolute Path to the log file."""
    return Path.home() / ".driver_backup" / "driver_backup.log"
