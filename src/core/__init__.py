"""
Core functionality for Crawl n Chat.
"""

from typing import Tuple
from src.core.router import AgentRouter
from src.vector_store.pinecone import PineconeWebsiteVectorStore
from src.core.logger import get_logger

logger = get_logger("core")

from src.core.settings import (
    DEFAULT_LLM_MODEL,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_ANSWER,
    API_TITLE,
    API_DESCRIPTION,
    API_VERSION,
    load_website_configs,
)


def initialize_services() -> Tuple[PineconeWebsiteVectorStore, AgentRouter]:
    """Initialize shared services used by both servers."""
    logger.info("Initializing shared services...")

    # Initialize vector store (Pinecone)
    logger.info("Initializing Pinecone vector store...")
    vector_store = PineconeWebsiteVectorStore(embedding_model=DEFAULT_EMBEDDING_MODEL)

    # Initialize agent router
    logger.info("Initializing agent router with LangGraph workflow...")
    agent_router = AgentRouter()

    logger.info("Shared services initialized successfully")
    return vector_store, agent_router


__all__ = [
    "AgentRouter",
    "DEFAULT_LLM_MODEL",
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_ANSWER",
    "API_TITLE",
    "API_DESCRIPTION",
    "API_VERSION",
    "load_website_configs",
    "get_logger",
    "initialize_services",
]
