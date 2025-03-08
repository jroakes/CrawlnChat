"""
Base class for vector stores in Crawl n Chat.

This module defines the abstract base class for vector store implementations,
providing a common interface for document storage, retrieval, and management.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union, Type, TypeVar

from src.vector_store.chunker import TextChunk
from src.core.logger import get_logger

logger = get_logger("vector_store")

# Type variable for the VectorStore class
T = TypeVar("T", bound="VectorStore")

# Import at class level to avoid circular imports
PineconeWebsiteVectorStore: Optional[Type[T]] = None


class VectorStore(ABC):
    """
    Abstract base class for vector stores.

    This class defines the interface that all vector store implementations must follow.
    It provides methods for:
    - Adding documents to the store
    - Querying for similar documents
    - Managing namespaces
    - Creating store instances
    """

    @abstractmethod
    def add_documents(self, documents: List[TextChunk], namespace: str) -> bool:
        """
        Add documents to the vector store.

        Args:
            documents: List of text chunks to add. Each chunk contains the text
                     and associated metadata.
            namespace: The namespace to store the documents in. This allows
                     partitioning the vector store by website or other criteria.

        Returns:
            bool: True if all documents were successfully added, False otherwise.

        Raises:
            Exception: If there is an error adding the documents. Specific
                      implementations may raise more specific exceptions.
        """
        pass

    @abstractmethod
    def query(
        self,
        query_text: str,
        namespace: str,
        top_k: int = 5,
        filter_dict: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query the vector store for similar documents.

        Args:
            query_text: The query text to find similar documents for.
            namespace: The namespace to search in. Only documents in this
                     namespace will be considered.
            top_k: Maximum number of results to return. Defaults to 5.
            filter_dict: Optional metadata filters to apply. Only documents
                        matching these filters will be returned.

        Returns:
            List[Dict[str, Any]]: List of search results, where each result is a
            dictionary containing:
                - text: str - The document text
                - metadata: Dict[str, Any] - Associated metadata
                - score: float - Similarity score (0-1)

        Raises:
            Exception: If there is an error querying the store. Specific
                      implementations may raise more specific exceptions.
        """
        pass

    @abstractmethod
    def delete_namespace(self, namespace: str) -> bool:
        """
        Delete a namespace and all its documents from the vector store.

        Args:
            namespace: The namespace to delete.

        Returns:
            bool: True if the namespace was successfully deleted, False otherwise.

        Raises:
            Exception: If there is an error deleting the namespace. Specific
                      implementations may raise more specific exceptions.
        """
        pass

    @abstractmethod
    def list_namespaces(self) -> List[str]:
        """
        List all namespaces currently in the vector store.

        Returns:
            List[str]: List of namespace names.

        Raises:
            Exception: If there is an error listing the namespaces. Specific
                      implementations may raise more specific exceptions.
        """
        pass

    @classmethod
    def get_instance(
        cls: Type[T], vector_store_type: str, embedding_model: str, **kwargs: Any
    ) -> T:
        """
        Factory method to create a vector store instance.

        This method provides a unified way to create instances of different
        vector store implementations.

        Args:
            vector_store_type: Type of vector store to create. Currently only
                             'pinecone' is supported.
            embedding_model: Name of the embedding model to use for converting
                           text to vectors.
            **kwargs: Additional arguments passed to the vector store constructor.
                     These are implementation-specific.

        Returns:
            VectorStore: An instance of the requested vector store type.

        Raises:
            ValueError: If the requested vector store type is not supported.
            Exception: If there is an error initializing the vector store.
                      Specific implementations may raise more specific exceptions.
        """
        global PineconeWebsiteVectorStore

        if vector_store_type == "pinecone":
            if PineconeWebsiteVectorStore is None:
                from .pinecone import PineconeWebsiteVectorStore as PWVS

                PineconeWebsiteVectorStore = PWVS
            return PineconeWebsiteVectorStore(embedding_model=embedding_model, **kwargs)
        else:
            raise ValueError(
                f"Unsupported vector store type: {vector_store_type}. "
                "Currently only 'pinecone' is supported."
            )
