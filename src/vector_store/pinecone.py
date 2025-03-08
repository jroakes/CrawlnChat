"""
Pinecone vector store implementation for Crawl n Chat using LangChain integrations.
"""

from typing import Dict, List, Optional, Any
import time
import uuid

from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_core.documents import Document
from pinecone import Pinecone, ServerlessSpec
from tqdm import tqdm

from src.core.settings import (
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    PINECONE_CLOUD,
    PINECONE_REGION,
)
from src.vector_store.chunker import TextChunk
from src.vector_store.base import VectorStore
from src.core.logger import get_logger

logger = get_logger("pinecone_vector_store")


class PineconeWebsiteVectorStore(VectorStore):
    """Vector store implementation using Pinecone with LangChain integration."""

    def __init__(
        self,
        embedding_model: str,
        api_key: str = PINECONE_API_KEY,
        cloud: str = PINECONE_CLOUD,
        region: str = PINECONE_REGION,
        index_name: str = PINECONE_INDEX_NAME,
    ):
        """
        Initialize the Pinecone vector store.

        Args:
            embedding_model: Model to use for generating embeddings.
            api_key: Pinecone API key.
            cloud: Cloud provider for Pinecone (e.g., 'aws', 'gcp').
            region: Region for Pinecone deployment (e.g., 'us-east-1').
            index_name: Name of the Pinecone index.
        """
        # Validate required configuration
        if not api_key:
            raise ValueError(
                "Pinecone API key not found. Please set the PINECONE_API_KEY environment variable."
            )

        self.embedding_model = embedding_model
        self.embedding_dimension = None
        self.api_key = api_key
        self.cloud = cloud
        self.region = region
        self.index_name = index_name

        # Initialize OpenAI embeddings
        self.embeddings = OpenAIEmbeddings(model=embedding_model)
        self.embedding_dimension = len(self.embeddings.embed_query('the'))


        logger.info(f"Initializing Pinecone with index name: {self.index_name}")

        # Initialize Pinecone client
        self.pc = Pinecone(api_key=api_key)

        # Check if index exists and create it if not
        if not self.index_exists():
            self.create_index()

        # Get the index
        index = self.pc.Index(self.index_name)

        # Connect to the LangChain Pinecone vector store
        self.store = PineconeVectorStore(index=index, embedding=self.embeddings)

        logger.info(f"Connected to Pinecone index: {self.index_name}")

    def index_exists(self) -> bool:
        """
        Check if the Pinecone index exists.

        Returns:
            True if index exists, False otherwise.
        """
        try:
            indexes = self.pc.list_indexes()
            return self.index_name in [index.name for index in indexes]
        except Exception as e:
            logger.error(f"Error checking if index exists: {e}")
            return False

    def create_index(self) -> bool:
        """
        Create the Pinecone index.

        Returns:
            True if successful, False otherwise.
        """
        try:
            # OpenAI embedding dimension is 1536 for text-embedding-ada-002
            dimension = self.embedding_dimension

            logger.info(
                f"Creating Pinecone index: {self.index_name} with dimension {dimension}"
            )
            self.pc.create_index(
                name=self.index_name,
                dimension=dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud=self.cloud, region=self.region),
            )

            # Wait for index to be ready
            logger.info("Waiting for index to be ready...")
            while not self.pc.describe_index(self.index_name).status["ready"]:
                time.sleep(1)

            logger.info(f"Created Pinecone index: {self.index_name}")
            return True
        except Exception as e:
            logger.error(f"Error creating Pinecone index: {e}")
            return False

    def add_documents(self, documents: List[TextChunk], namespace: str) -> bool:
        """
        Add documents to the Pinecone index.

        Args:
            documents: List of text chunks to add.
            namespace: The namespace to store the documents in.

        Returns:
            True if successful, False otherwise.
        """
        try:
            # Convert TextChunk objects to LangChain Document objects
            langchain_docs = []
            for doc in documents:
                langchain_docs.append(
                    Document(page_content=doc.text, metadata=doc.metadata)
                )
            
            # Log start of embedding process - this is the time-consuming step
            if langchain_docs:
                logger.info(f"Generating embeddings for {len(langchain_docs)} documents - this may take some time...")

            # Add documents to Pinecone using batched processing
            batch_size = 100
            for i in tqdm(range(0, len(langchain_docs), batch_size), desc="Uploading document batches"):
                batch = langchain_docs[i : i + batch_size]

                # Use LangChain to add documents
                self.store.add_documents(documents=batch, namespace=namespace)

                logger.info(
                    f"Added batch of {len(batch)} documents to namespace '{namespace}'"
                )

            return True

        except Exception as e:
            logger.error(f"Error adding documents to Pinecone: {e}")
            return False

    def query(
        self,
        query_text: str,
        namespace: str,
        top_k: int = 5,
        filter_dict: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query the Pinecone index for similar documents.

        Args:
            query_text: The query text.
            namespace: The namespace to search in.
            top_k: Number of results to return.
            filter_dict: Optional metadata filters.

        Returns:
            List of search results with text and metadata.
        """
        try:
            # Prepare filter if provided
            filter_dict = filter_dict or {}

            # Query using LangChain
            results = self.store.similarity_search_with_score(
                query=query_text,
                k=top_k,
                namespace=namespace,
                filter=filter_dict if filter_dict else None,
            )

            # Format results to maintain the same interface
            formatted_results = []
            for doc, score in results:
                formatted_results.append(
                    {"text": doc.page_content, "score": score, "metadata": doc.metadata}
                )

            return formatted_results

        except Exception as e:
            logger.error(f"Error querying Pinecone: {e}")
            return []

    def delete_namespace(self, namespace: str) -> bool:
        """
        Delete a namespace from the Pinecone index.

        Args:
            namespace: The namespace to delete.

        Returns:
            True if successful, False otherwise.
        """
        try:
            # Access the underlying Pinecone index directly
            # PineconeVectorStore doesn't have a vectorstore attribute in newer versions
            pinecone_index = self.pc.Index(self.index_name)
            pinecone_index.delete(delete_all=True, namespace=namespace)

            logger.info(f"Deleted namespace '{namespace}' from Pinecone")
            return True
        except Exception as e:
            logger.error(f"Error deleting namespace from Pinecone: {e}")
            return False

    def list_namespaces(self) -> List[str]:
        """
        List all namespaces in the Pinecone index.

        Returns:
            List of namespace names.
        """
        try:
            # Access the underlying Pinecone index directly
            # PineconeVectorStore doesn't have an index attribute in newer versions
            pinecone_index = self.pc.Index(self.index_name)
            stats = pinecone_index.describe_index_stats()

            return list(stats.get("namespaces", {}).keys())
        except Exception as e:
            logger.error(f"Error listing Pinecone namespaces: {e}")
            return []
