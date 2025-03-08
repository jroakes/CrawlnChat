"""
Asynchronous content fetching module for Crawl n Chat.

This module provides functionality for fetching and processing web content asynchronously,
with support for rate limiting, content type filtering, and content conversion.
"""

import os
import asyncio
import time
from typing import Dict, List, Tuple, Any
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm
from markitdown import MarkItDown

from src.core.settings import CRAWL_RATE_LIMIT, USER_AGENT
from src.core.logger import get_logger

logger = get_logger("fetcher")

# Define file extensions and content types to skip
SKIP_EXTENSIONS: List[str] = [
    # Images
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tiff",
    ".webp",
    ".svg",
    # Audio
    ".mp3",
    ".wav",
    ".ogg",
    ".m4a",
    ".flac",
    ".aac",
    # Video
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm",
    ".flv",
    ".wmv",
    # Documents (except PDF which we handle)
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    # Archives
    ".zip",
    ".rar",
    ".tar",
    ".gz",
    ".7z",
    # Data
    ".csv",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    # Code
    ".js",
    ".css",
    ".ts",
    ".jsx",
    ".tsx",
    # Fonts
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
    ".eot",
]

SKIP_CONTENT_TYPES: List[str] = [
    "image/",
    "audio/",
    "video/",
    "application/zip",
    "application/x-rar",
    "application/x-tar",
    "application/x-gzip",
    "application/x-7z-compressed",
    "application/javascript",
    "text/css",
    "font/",
    "application/font-woff",
    "application/font-sfnt",
    "application/vnd.ms-fontobject",
]


class AsyncContentFetcher:
    """
    Asynchronous content fetcher that respects rate limits.

    This class handles fetching web content with:
    - Rate limiting to prevent overwhelming servers
    - Content type filtering
    - Automatic retries on failure
    - Content conversion to text
    """

    def __init__(self, rate_limit: int = CRAWL_RATE_LIMIT) -> None:
        """
        Initialize the content fetcher.

        Args:
            rate_limit: Maximum number of requests per second. Defaults to CRAWL_RATE_LIMIT.
        """
        self.rate_limit = rate_limit
        # Allow 2x concurrent connections
        self.semaphore = asyncio.Semaphore(self.rate_limit * 2)
        self.headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml,application/pdf;q=0.9,*/*;q=0.8",
        }
        self.markitdown = MarkItDown()

    def _should_skip_url(self, url: str) -> bool:
        """
        Check if a URL should be skipped based on file extension.

        Args:
            url: The URL to check.

        Returns:
            bool: True if the URL should be skipped, False otherwise.
        """
        # Extract the file extension from the URL
        # Handle URL parameters by parsing only the path part
        path = url.split("?")[0].split("#")[0]
        extension = os.path.splitext(path)[1].lower()

        return extension in SKIP_EXTENSIONS

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _fetch_url(
        self, session: aiohttp.ClientSession, url: str
    ) -> Tuple[str, str, str]:
        """
        Fetch content from a URL with automatic retries.

        Args:
            session: The aiohttp client session.
            url: The URL to fetch.

        Returns:
            Tuple[str, str, str]: A tuple of (url, content_type, content).
                If fetching fails, content_type and content will be empty strings.
        """
        # Skip URLs with file extensions we don't want to process
        if self._should_skip_url(url):
            logger.info(f"Skipping URL with disallowed extension: {url}")
            return url, "", ""

        async with self.semaphore:
            try:
                async with session.get(
                    url, headers=self.headers, timeout=30, ssl=False
                ) as response:
                    response.raise_for_status()
                    content_type = response.headers.get("Content-Type", "").lower()

                    # Skip disallowed content types
                    if any(ct in content_type for ct in SKIP_CONTENT_TYPES):
                        logger.info(
                            f"Skipping unsupported content type: {content_type} for {url}"
                        )
                        return url, content_type, ""

                    content_bytes = await response.read()
                    content = await self._process_content(
                        url, content_type, content_bytes
                    )
                    await asyncio.sleep(1 / self.rate_limit)  # Rate limiting
                    return url, content_type, content

            except aiohttp.ClientError as e:
                logger.error(f"Error fetching {url}: {e}")
                return url, "", ""
            except asyncio.TimeoutError:
                logger.error(f"Timeout fetching {url}")
                return url, "", ""
            except Exception as e:
                logger.error(f"Unexpected error fetching {url}: {e}")
                return url, "", ""

    async def _process_content(
        self, url: str, content_type: str, content_bytes: bytes
    ) -> str:
        """
        Process and convert content based on its type.

        Args:
            url: The source URL.
            content_type: The content's MIME type.
            content_bytes: The raw content bytes.

        Returns:
            str: The processed content as text, or empty string if processing fails.
        """
        try:
            # Only process HTML and PDF files
            if "text/html" in content_type or "application/xhtml+xml" in content_type:
                file_extension = ".html"
            elif "application/pdf" in content_type:
                file_extension = ".pdf"
            else:
                logger.info(
                    f"Skipping unsupported content type: {content_type} for {url}"
                )
                return ""

            # Create temporary file with appropriate extension
            temp_file_path = f"temp_{time.time()}{file_extension}"
            with open(temp_file_path, "wb") as f:
                f.write(content_bytes)

            # Convert content using Markitdown
            result = self.markitdown.convert(temp_file_path)
            content = result.text_content

            # Clean up the temporary file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

            return content

        except Exception as e:
            logger.error(f"Error processing content with Markitdown at {url}: {e}")

            # Fallback to raw content if Markitdown fails
            if "text/html" in content_type or "application/xhtml+xml" in content_type:
                return content_bytes.decode("utf-8", errors="replace")
            return ""

    async def fetch_urls(self, urls: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Fetch content from multiple URLs in parallel.

        Args:
            urls: List of URLs to fetch.

        Returns:
            Dict[str, Dict[str, Any]]: Dictionary mapping URLs to their content information.
            Each value contains:
                - content_type: str - The MIME type of the content
                - content: str - The processed text content
                - error: Optional[str] - Error message if fetching failed
        """
        # Filter out URLs with extensions we want to skip
        filtered_urls = [url for url in urls if not self._should_skip_url(url)]
        if len(filtered_urls) < len(urls):
            logger.info(
                f"Filtered out {len(urls) - len(filtered_urls)} URLs with disallowed extensions"
            )

        results: Dict[str, Dict[str, Any]] = {}

        # Create a connector with ssl=False
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [self._fetch_url(session, url) for url in filtered_urls]

            # Use tqdm to show progress
            for url, content_type, content in tqdm(
                await asyncio.gather(*tasks),
                total=len(filtered_urls),
                desc="Fetching URLs",
            ):
                results[url] = {
                    "content_type": content_type,
                    "content": content,
                    "error": None if content else "Failed to fetch or process content",
                }

        return results
