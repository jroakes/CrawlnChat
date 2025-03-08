"""
XML Sitemap parsing module for Crawl n Chat.
"""

import re
import traceback
from typing import List, Optional, Set, Tuple, Union
import httpx
from lxml import etree
from tenacity import retry, stop_after_attempt, wait_exponential
import brotli
from pydantic import HttpUrl

from src.core.settings import USER_AGENT
from src.core.logger import get_logger

logger = get_logger("sitemap")


class SitemapParser:
    """Parser for XML sitemaps that extracts URLs for crawling."""

    def __init__(self):
        """Initialize the sitemap parser."""
        # Disable SSL verification with verify=False
        # Configure client with custom headers to prevent bot detection
        self.client = httpx.Client(
            timeout=30.0,
            verify=False,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xml,application/xhtml+xml,*/*",
                "Accept-Encoding": "gzip, deflate, br",  # Support brotli encoding
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
        )

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit. Close the client."""
        self.client.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def _fetch_sitemap(self, url: Union[str, HttpUrl, 'httpx.URL']) -> bytes:
        """
        Fetch a sitemap from a URL.

        Args:
            url: The URL of the sitemap. Can be a string, httpx.URL or pydantic.HttpUrl.

        Returns:
            The raw XML content of the sitemap.
        """
        # Convert pydantic.HttpUrl to string if needed
        url_str = str(url)
        
        logger.debug(f"Fetching sitemap from {url_str}")

        try:
            response = self.client.get(url_str)
            response.raise_for_status()

            # Log response headers for debugging
            logger.debug(f"Response headers: {dict(response.headers)}")

            # Check for Brotli encoding
            content_encoding = response.headers.get("Content-Encoding", "").lower()
            content = response.content

            if "br" in content_encoding:
                logger.debug("Decompressing Brotli-encoded response")
                try:
                    content = brotli.decompress(content)
                except brotli.error as e:
                    logger.info(f"Failed to decompress Brotli content: {e} (continuing with raw content)")
                    # Continue with raw content - the XML parser may still be able to handle it
                    # In some cases, Cloudflare might say it's Brotli but actually send readable content

            logger.debug(f"Sitemap content length: {len(content)} bytes")
            # Log a small sample of the content to debug format issues
            if len(content) > 0:
                sample = (
                    content[:200].decode("utf-8", errors="replace")
                    if isinstance(content, bytes)
                    else content[:200]
                )
                logger.debug(f"Sitemap content sample: {sample}...")

            return content

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP status error fetching sitemap {url_str}: {e.response.status_code} - {e}"
            )
            if e.response.status_code == 403:
                logger.error("Access forbidden - site may be blocking crawlers")
            elif e.response.status_code == 404:
                logger.error("Sitemap not found - check URL")

            # Log full response for debugging
            if hasattr(e, "response"):
                logger.debug(f"Error response headers: {dict(e.response.headers)}")
                logger.debug(f"Error response content: {e.response.text[:500]}")

            raise
        except Exception as e:
            logger.error(f"Error fetching sitemap {url_str}: {e}")
            logger.debug(f"Exception details: {traceback.format_exc()}")
            raise

    def _parse_sitemap_urls(self, xml_content: bytes) -> Tuple[List[str], List[str]]:
        """
        Parse URLs from a sitemap XML.

        Args:
            xml_content: The raw XML content of the sitemap.

        Returns:
            A tuple of (page_urls, sitemap_urls).
        """
        try:
            # Parse XML
            root = etree.fromstring(xml_content)

            # Handle multiple namespaces in sitemaps
            namespaces = {
                "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
                "xhtml": "http://www.w3.org/1999/xhtml",
            }

            # Extract page URLs
            page_urls = []
            for loc in root.xpath("//sm:url/sm:loc", namespaces=namespaces):
                url = loc.text.strip() if loc.text else ""
                if url:
                    page_urls.append(url)

            # Extract URLs to other sitemaps
            sitemap_urls = []
            for loc in root.xpath("//sm:sitemap/sm:loc", namespaces=namespaces):
                url = loc.text.strip() if loc.text else ""
                if url:
                    sitemap_urls.append(url)

            return page_urls, sitemap_urls

        except etree.XMLSyntaxError as e:
            logger.error(f"XML parsing error: {e}")
            # Try to salvage malformed XML
            try:
                # Try again with more lenient HTML parser
                parser = etree.HTMLParser()
                tree = etree.fromstring(xml_content, parser)
                urls = []
                for elem in tree.xpath("//loc"):
                    if elem.text:
                        urls.append(elem.text.strip())
                return urls, []
            except Exception as inner_e:
                logger.error(f"Secondary parsing failed: {inner_e}")

            # If malformed, log content for debugging
            try:
                content_str = xml_content.decode("utf-8", errors="replace")
                logger.debug(f"Malformed XML content: {content_str[:500]}...")
            except:
                pass

            return [], []
        except Exception as e:
            logger.error(f"Error parsing sitemap: {e}")
            return [], []

    def process_sitemap(
        self,
        sitemap_url: Union[str, HttpUrl, 'httpx.URL'],
        exclude_patterns: Optional[List[str]] = None,
        include_only_patterns: Optional[List[str]] = None,
    ) -> Set[str]:
        """
        Process a sitemap URL and extract all page URLs.

        Args:
            sitemap_url: The URL of the sitemap. Can be string, HttpUrl or httpx.URL.
            exclude_patterns: List of regex patterns for URLs to exclude.
            include_only_patterns: List of regex patterns for URLs to include.

        Returns:
            A set of page URLs found in the sitemap.
        """
        exclude_patterns = exclude_patterns or []
        include_only_patterns = include_only_patterns or []

        # Compile regex patterns
        exclude_regex = [re.compile(pattern) for pattern in exclude_patterns]
        include_only_regex = [re.compile(pattern) for pattern in include_only_patterns]

        all_page_urls = set()
        processed_sitemaps = set()
        
        # Convert sitemap_url to string for consistent handling
        sitemap_url_str = str(sitemap_url)
        pending_sitemaps = {sitemap_url_str}

        while pending_sitemaps:
            current_sitemap = pending_sitemaps.pop()

            # Skip if already processed
            if current_sitemap in processed_sitemaps:
                continue

            logger.info(f"Processing sitemap: {current_sitemap}")
            processed_sitemaps.add(current_sitemap)

            try:
                xml_content = self._fetch_sitemap(current_sitemap)
                page_urls, new_sitemap_urls = self._parse_sitemap_urls(xml_content)

                # Filter URLs
                for url in page_urls:
                    # Skip if excluded
                    if any(pattern.search(url) for pattern in exclude_regex):
                        continue

                    # Skip if not included (when include patterns are specified)
                    if include_only_regex and not any(
                        pattern.search(url) for pattern in include_only_regex
                    ):
                        continue

                    all_page_urls.add(url)

                # Add new sitemaps to process
                pending_sitemaps.update(new_sitemap_urls)

            except Exception as e:
                logger.error(f"Error processing sitemap {current_sitemap}: {e}")

        logger.info(f"Found {len(all_page_urls)} pages in sitemap {sitemap_url_str}")
        return all_page_urls
