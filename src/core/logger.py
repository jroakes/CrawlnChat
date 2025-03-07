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

# Remove default logger
logger.remove()

# Add stdout handler with INFO level
logger.add(
    sys.stdout,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)

# Add file handler with DEBUG level
logger.add(
    logs_dir / "crawl-n-chat.log",
    rotation="10 MB",
    retention="1 week",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
)

# Set third-party library loggers to WARNING or higher
# This will silence most of the noisy DEBUG and INFO messages
LOGGERS_TO_SILENCE = [
    # Pinecone related
    "pinecone",
    "pinecone_plugins",
    "pinecone_plugins.inference",
    "pinecone_plugins.inference.plugin",
    "pinecone_text",
    "pinecone_plugin_interface",
    # HTTP related
    "httpx",
    "httpcore",
    "urllib3",
    # Standard logging
    "logging",
]

# Set all specified loggers to WARNING level
for logger_name in LOGGERS_TO_SILENCE:
    logging.getLogger(logger_name).setLevel(logging.WARNING)


# Intercept the standard logging library and redirect it through loguru
class InterceptHandler(logging.Handler):
    """
    Intercepts standard logging messages and redirects them through loguru.

    This handler allows seamless integration between the standard logging library
    and loguru by intercepting logging records and properly formatting them
    for loguru's logging system.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """
        Process and emit a logging record through loguru.

        Args:
            record: The logging record to process and emit.
        """
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
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
UVICORN_LOGGERS = [
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
]

for uvicorn_logger in UVICORN_LOGGERS:
    logging_logger = logging.getLogger(uvicorn_logger)
    logging_logger.handlers = [InterceptHandler()]
    # We want to see uvicorn startup messages
    logging_logger.propagate = False


def get_logger(name: str) -> Logger:
    """
    Get a logger with the given name.

    Args:
        name: The name to bind to the logger.

    Returns:
        A loguru logger instance bound with the given name.
    """
    return logger.bind(name=name)
