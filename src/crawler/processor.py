"""
Website crawling and processing module for Crawl n Chat.
"""

from typing import Dict, Any

from src.crawler.sitemap import SitemapParser
from src.crawler.fetcher import AsyncContentFetcher
from src.vector_store.chunker import TextChunker
from src.vector_store.pinecone import PineconeWebsiteVectorStore
from src.core.settings import DEFAULT_EMBEDDING_MODEL, CrawlnChatConfig
from src.core.logger import get_logger

logger = get_logger("crawler_processor")


async def crawl_website(
    website_config, vector_store: PineconeWebsiteVectorStore, recrawl: bool = False
) -> Dict[str, Any]:
    """
    Crawl a website and store its content in the vector database.

    Args:
        website_config: Configuration for the website to crawl.
        vector_store: The vector store instance.
        recrawl: Whether to recrawl the website if it already exists.

    Returns:
        A dictionary with crawl statistics.
    """
    try:
        # Create namespace from website name
        namespace = website_config.name.lower().replace(" ", "_")

        # Check if namespace exists
        namespaces = vector_store.list_namespaces()

        if namespace in namespaces and not recrawl:
            logger.info(
                f"Namespace '{namespace}' already exists, skipping (use --recrawl to override)"
            )
            return {
                "namespace": namespace,
                "status": "skipped",
                "reason": "already_exists",
            }

        # Delete existing namespace if recrawling
        if namespace in namespaces and recrawl:
            logger.info(f"Deleting existing namespace '{namespace}' for recrawl")
            vector_store.delete_namespace(namespace)

        # Process the sitemap
        logger.info(
            f"Processing sitemap for {website_config.name}: {website_config.xml_sitemap}"
        )
        with SitemapParser() as parser:
            page_urls = parser.process_sitemap(
                sitemap_url=website_config.xml_sitemap,
                exclude_patterns=website_config.exclude_patterns,
                include_only_patterns=website_config.include_only_patterns,
            )

        if not page_urls:
            logger.error(f"No pages found in sitemap: {website_config.xml_sitemap}")
            return {
                "namespace": namespace,
                "status": "error",
                "reason": "no_pages_found",
            }

        # Fetch content
        logger.info(f"Fetching {len(page_urls)} pages for {website_config.name}")
        fetcher = AsyncContentFetcher()
        results = await fetcher.fetch_urls(list(page_urls))

        if not results:
            logger.error(f"Failed to fetch any content for {website_config.name}")
            return {"namespace": namespace, "status": "error", "reason": "fetch_failed"}

        # Process content to chunks (content is already in markdown format from the fetcher)
        logger.info(f"Processing content for {website_config.name}")
        chunker = TextChunker()

        all_chunks = []
        errors = []

        for url, data in results.items():
            try:
                # Skip the redundant markdown conversion since data["content"] is already markdown
                markdown = data["content"]

                if not markdown:
                    errors.append(f"Failed to process content for {url}")
                    continue

                # Create metadata
                metadata = {
                    "source": url,
                    "title": data.get("title", ""),
                    "crawl_timestamp": str(data.get("timestamp", "")),
                    "website_name": website_config.name,
                }

                # Chunk the markdown
                chunks = chunker.chunk_text(markdown, metadata)
                all_chunks.extend(chunks)

            except Exception as e:
                errors.append(f"Error processing {url}: {str(e)}")
                logger.error(f"Error processing {url}: {e}")

        if not all_chunks:
            logger.error(f"Failed to create any chunks for {website_config.name}")
            return {
                "namespace": namespace,
                "status": "error",
                "reason": "no_chunks_created",
            }

        # Note: This is a synchronous operation within an async context.
        # It's acceptable since vector store operations aren't the main bottleneck
        # compared to the network-bound operations for fetching content.
        logger.info(
            f"Storing {len(all_chunks)} chunks for {website_config.name} in namespace '{namespace}'"
        )
        success = vector_store.add_documents(all_chunks, namespace)

        if not success:
            logger.error(f"Failed to store chunks for {website_config.name}")
            return {
                "namespace": namespace,
                "status": "error",
                "reason": "storage_failed",
            }

        logger.info(
            f"Successfully processed {website_config.name}: {len(results)} pages, {len(all_chunks)} chunks"
        )
        return {
            "namespace": namespace,
            "status": "success",
            "pages_crawled": len(results),
            "chunks_stored": len(all_chunks),
            "errors": errors,
        }

    except Exception as e:
        logger.error(f"Error crawling {website_config.name}: {e}")
        return {
            "namespace": website_config.name.lower().replace(" ", "_"),
            "status": "error",
            "reason": str(e),
        }


async def process_websites(config_file: str, recrawl: bool = False) -> None:
    """
    Process all websites in a configuration file.

    Args:
        config_file: Path to the configuration file.
        recrawl: Whether to recrawl websites that already exist.
    """
    try:
        # Load configuration
        config = CrawlnChatConfig.from_file(config_file)

        # Initialize vector store (Pinecone) early to ensure proper initialization
        logger.info("Initializing Pinecone vector store...")
        vector_store = PineconeWebsiteVectorStore(
            embedding_model=DEFAULT_EMBEDDING_MODEL
        )

        # Process websites
        results = []
        for website in config.websites:
            logger.info(f"Processing website: {website.name}")
            result = await crawl_website(website, vector_store, recrawl)
            results.append(result)

        # Log crawl summary using debug level
        logger.debug("Crawl Summary:")
        logger.debug("-" * 50)
        for result in results:
            status = result["status"]
            namespace = result["namespace"]

            if status == "success":
                logger.debug(
                    f"✅ {namespace}: {result['pages_crawled']} pages, {result['chunks_stored']} chunks"
                )
            elif status == "skipped":
                logger.debug(f"⏭️  {namespace}: Skipped ({result['reason']})")
            else:
                logger.debug(f"❌ {namespace}: Failed ({result['reason']})")
        logger.debug("-" * 50)

        # Add a clear completion message that's always visible
        logger.info("✅ Website crawling process completed successfully")

        return results

    except Exception as e:
        logger.error(f"Error processing websites: {e}")
        raise
