"""
Application settings for Crawl n Chat.

This module manages all configuration settings for the application, including:
- Environment variables
- API keys and credentials
- Server configuration
- Crawling parameters
- Model settings
- Website configurations
"""

import os
from typing import Dict, List, Optional, Union, Literal, Any
from pydantic import BaseModel, Field, HttpUrl
from dotenv import load_dotenv
import json
import yaml
from core.logger import get_logger

# Set up logger
logger = get_logger("config_settings")

# Load environment variables
load_dotenv()

__version__ = "0.1.0"


# About
API_TITLE: str = os.getenv("API_TITLE", "Crawl n Chat API")
API_DESCRIPTION: str = os.getenv(
    "API_DESCRIPTION", "API for chatting with website content"
)
API_VERSION: str = __version__

# Basic authentication
ADMIN_PASSWORD: Optional[str] = os.getenv("ADMIN_PASSWORD")

# API keys
OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
PINECONE_API_KEY: Optional[str] = os.getenv("PINECONE_API_KEY")
PINECONE_CLOUD: str = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION: str = os.getenv("PINECONE_REGION", "us-east-1")
PINECONE_INDEX_NAME: str = os.getenv("PINECONE_INDEX_NAME", "crawl-n-chat")

# Crawling configuration
CRAWL_RATE_LIMIT: int = int(os.getenv("CRAWL_RATE_LIMIT", "5"))
USER_AGENT: str = os.getenv(
    "USER_AGENT", "CrawlnChat/1.0 (+https://github.com/yourusername/crawl-n-chat)"
)

# Vector database configuration
DEFAULT_EMBEDDING_MODEL: str = os.getenv(
    "DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small"
)
VECTOR_DB_TYPE: Literal["pinecone"] = "pinecone"  # We only support Pinecone for now

# LLM configuration
DEFAULT_LLM_MODEL: str = os.getenv("DEFAULT_LLM_MODEL", "gpt-4")
DEFAULT_ANTHROPIC_MODEL: str = os.getenv(
    "DEFAULT_ANTHROPIC_MODEL", "claude-3-opus-20240229"
)

# API configuration
SERVER_URL: str = os.getenv("SERVER_URL", "http://localhost:8000")
FASTAPI_PORT: int = int(os.getenv("FASTAPI_PORT", "8000"))
MCP_PORT: int = int(os.getenv("MCP_PORT", "8001"))

# Default configuration file paths
DEFAULT_CONFIG_PATHS: List[str] = [
    "websites.json",
    "websites.yaml",
    "websites.yml",
    "config/websites.json",
    "config/websites.yaml",
    "config/websites.yml",
]

# Default answer for when no sources are found
DEFAULT_ANSWER: str = "I'm sorry, I couldn't find a good answer to your question."
BRAND_GUIDELINES_FILE: Optional[str] = os.getenv("BRAND_GUIDELINES_FILE")
NUM_RAG_SOURCES: int = int(os.getenv("NUM_RAG_SOURCES", "5"))


class WebsiteConfig(BaseModel):
    """
    Configuration model for a website to crawl.

    This model defines the parameters for crawling and processing a website,
    including URL patterns, content freshness, and metadata.

    Attributes:
        name: The name of the website for identification and namespacing
        xml_sitemap: URL of the website's XML sitemap for crawling
        description: Description of the website's content for context
        freshness_days: Number of days before content is considered stale
        exclude_patterns: List of URL patterns to exclude from crawling
        include_only_patterns: List of URL patterns to exclusively include
    """

    name: str = Field(..., description="The name of the website for identification")
    xml_sitemap: HttpUrl = Field(..., description="URL of the website's XML sitemap")
    description: str = Field(..., description="Description of the website's content")
    freshness_days: int = Field(
        default=7, description="Number of days before content is considered stale", ge=1
    )
    exclude_patterns: List[str] = Field(
        default_factory=list, description="URL patterns to exclude from crawling"
    )
    include_only_patterns: List[str] = Field(
        default_factory=list,
        description="URL patterns to exclusively include in crawling",
    )


class CrawlnChatConfig(BaseModel):
    """
    Main configuration model for Crawl n Chat.

    This model represents the complete configuration for the application,
    containing a list of websites to crawl and process.

    Attributes:
        websites: List of website configurations to process
    """

    websites: List[WebsiteConfig] = Field(
        ..., description="List of websites to crawl and process"
    )

    @classmethod
    def from_file(cls, file_path: str) -> "CrawlnChatConfig":
        """
        Load configuration from a JSON or YAML file.

        This method handles loading and parsing configuration files in either
        JSON or YAML format, validating the content against the model schema.

        Args:
            file_path: Path to the configuration file. Must end in .json,
                      .yaml, or .yml.

        Returns:
            CrawlnChatConfig: The loaded and validated configuration object.

        Raises:
            ValueError: If the file format is not supported (.json, .yaml, .yml)
            FileNotFoundError: If the specified file does not exist
            ValidationError: If the configuration data is invalid
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        if file_path.endswith(".json"):
            with open(file_path, "r") as f:
                data = json.load(f)
        elif file_path.endswith((".yaml", ".yml")):
            with open(file_path, "r") as f:
                data = yaml.safe_load(f)
        else:
            raise ValueError(
                f"Unsupported file format: {file_path}. "
                "Must be .json, .yaml, or .yml"
            )

        return cls(**data)


def load_website_configs(config_file: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Load website configurations from a JSON or YAML file.

    This function attempts to load website configurations from either a specified
    file or from a list of default locations. It handles both JSON and YAML
    formats and validates the configuration structure.

    Args:
        config_file: Optional path to the configuration file. If None,
                    searches through DEFAULT_CONFIG_PATHS.

    Returns:
        List[Dict[str, Any]]: List of website configurations as dictionaries.
                             Returns an empty list if no valid configuration
                             is found.

    Note:
        While this function returns raw dictionaries, the data should be
        validated using the WebsiteConfig model before use in the application.
    """
    # Determine which paths to check
    paths_to_check = [config_file] if config_file else DEFAULT_CONFIG_PATHS

    # Check each path
    for path in paths_to_check:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    if path.endswith((".yaml", ".yml")):
                        config = yaml.safe_load(f)
                    else:
                        config = json.load(f)

                websites = config.get("websites", [])
                logger.info(
                    f"Loaded {len(websites)} website configurations from {path}"
                )
                return websites
            except Exception as e:
                logger.error(f"Error loading website configurations from {path}: {e}")

    logger.warning("No website configurations found, using empty list")
    return []
