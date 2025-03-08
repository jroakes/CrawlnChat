"""
Logging utility for Crawl n Chat.
"""

import sys
import logging
from pathlib import Path
from loguru import logger
from loguru._logger import Logger

# Create logs directory if it doesn't exist
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Global handler IDs for reconfiguration
_stdout_handler_id = None
_file_handler_id = None

def configure_logging(level="ERROR"):
    """
    Configure logging with the specified level for stdout.
    File logging always remains at DEBUG level.
    
    Args:
        level: Log level for stdout (default: ERROR)
    """
    global _stdout_handler_id, _file_handler_id
    
    # Remove existing handlers
    logger.remove()
    
    # Configure stdout handler with the specified level
    _stdout_handler_id = logger.add(
        sys.stdout,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    
    # Configure file handler with DEBUG level
    _file_handler_id = logger.add(
        logs_dir / "crawl-n-chat.log",
        rotation="10 MB",
        retention="1 week",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )

    # Set third-party library loggers to WARNING
    LOGGERS_TO_SILENCE = [
        "pinecone", "pinecone_plugins", "pinecone_plugins.inference", 
        "pinecone_plugins.inference.plugin", "pinecone_text", 
        "pinecone_plugin_interface", "httpx", "httpcore", "urllib3", "logging",
    ]

    for logger_name in LOGGERS_TO_SILENCE:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

# Initialize logging with default ERROR level
configure_logging("ERROR")

# Intercept the standard logging library and redirect it through loguru
class InterceptHandler(logging.Handler):
    """Intercepts standard logging messages and redirects them through loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        """Process and emit a logging record through loguru."""
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

# Add the interceptor to the Python logging system
logging.basicConfig(handlers=[InterceptHandler()], level=0)

# Configure uvicorn loggers to use our interceptor
for uvicorn_logger in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
    logging_logger = logging.getLogger(uvicorn_logger)
    logging_logger.handlers = [InterceptHandler()]
    logging_logger.propagate = False

def get_logger(name: str) -> Logger:
    """Get a logger with the given name."""
    return logger.bind(name=name)
