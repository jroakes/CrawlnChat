"""
Text chunking module for Crawl n Chat using LangChain text splitters.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.core.logger import get_logger

logger = get_logger("chunker")


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata."""

    text: str
    metadata: Dict[str, str]


class TextChunker:
    """Splits text into smaller chunks for embedding and vector storage using LangChain's splitters."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None,
    ):
        """
        Initialize the text chunker.

        Args:
            chunk_size: Target size of each chunk in characters.
            chunk_overlap: Number of characters to overlap between chunks.
            separators: List of separators to recursively split on, default is ["\n\n", "\n", " ", ""]
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", " ", ""]

        # Initialize the LangChain text splitter
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=self.separators,
        )

    def chunk_text(
        self, text: str, metadata: Optional[Dict[str, str]] = None
    ) -> List[TextChunk]:
        """
        Split text into chunks with metadata.

        Args:
            text: The text to chunk.
            metadata: Metadata to associate with each chunk.

        Returns:
            List of TextChunk objects.
        """
        if not text:
            logger.warning("Empty text provided for chunking")
            return []

        base_metadata = metadata or {}

        # Use LangChain's splitter to split the text
        splits = self.splitter.split_text(text)

        # Create TextChunk objects
        result = []
        for i, chunk_text in enumerate(splits):
            chunk_metadata = base_metadata.copy()
            chunk_metadata["chunk_index"] = str(i)
            chunk_metadata["chunk_count"] = str(len(splits))

            # Add the first few characters as a preview
            preview_length = min(100, len(chunk_text))
            chunk_metadata["preview"] = chunk_text[:preview_length].replace("\n", " ")

            result.append(TextChunk(text=chunk_text, metadata=chunk_metadata))

        logger.info(f"Split text into {len(result)} chunks")
        return result
