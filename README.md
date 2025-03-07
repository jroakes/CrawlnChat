# Crawl n Chat

A modular web crawling and chat system that allows for ingesting website content through XML sitemaps, converting to vector embeddings, and providing AI-powered chat interfaces through multiple frontend options.

## Features

- **Web Crawling**: Asynchronously crawl websites from XML sitemaps, with built-in HTML-to-markdown conversion
- **Vector Storage**: Efficient text chunking and embedding storage in Pinecone for high-performance similarity search
- **Agentic Routing**: LangGraph-powered intelligent question routing that treats each website as a specialized knowledge tool
- **Multiple Interfaces**: FastAPI (Swagger UI) and MCP (Anthropic Claude) frontends
- **Brand Compliance**: Automated review of responses against brand guidelines
- **Configuration Flexibility**: Support for both JSON and YAML configuration formats
- **Source Attribution**: Automatic inclusion of source URLs in responses for attribution and verification
- **Enhanced Logging**: Detailed logging of agent interactions, tool usage, and response generation

## System Architecture

```
┌─────────────────┐      ┌─────────────────┐      
│                 │      │                 │      
│  Configuration  │──────▶  Crawler Engine │──────┐      
│  (JSON/YAML)    │      │  (Async)        │      │
│                 │      │                 │      │
└─────────────────┘      └─────────────────┘      │
                                                  │
                                                  ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│                 │      │                 │      │                 │
│  Pinecone       │◀─────┤  Embedding      │◀─────┤  Vector Store   │
│  Vector Store   │      │  Generation     │      │  Chunker        │
│                 │      │                 │      │                 │
└────────┬────────┘      └─────────────────┘      └─────────────────┘
         │
         │
         ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│                 │      │                 │      │                 │
│  Agent Router   │──────▶  Response       │──────▶  Brand Review   │
│  (LangGraph)    │      │  Formulation    │      │  (LLM)          │
│                 │      │                 │      │                 │
└─────────────────┘      └─────────────────┘      └────────┬────────┘
                                                           │
                                                           ▼
                                     ┌─────────────────┐      ┌─────────────────┐
                                     │                 │      │                 │
                                     │  FastAPI        │      │  MCP            │
                                     │  (Swagger UI)   │      │  (Claude)       │
                                     │                 │      │                 │
                                     └─────────────────┘      └─────────────────┘
```

## Installation

```bash
# Clone the repository
git clone https://github.com/jroakes/crawl-n-chat.git
cd crawl-n-chat

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env file with your API keys and configuration
```

## Configuration

Create a website configuration file in either JSON or YAML format:

### JSON Configuration Example

```json
{
  "websites": [
    {
      "name": "Example Documentation",
      "xml_sitemap": "https://example.com/sitemap.xml",
      "description": "Documentation for the Example service and API",
      "freshness_days": 7,
      "exclude_patterns": [
        "https://example.com/outdated/.*"
      ],
      "include_only_patterns": [
        "https://example.com/docs/.*"
      ]
    },
    {
      "name": "Support Knowledge Base",
      "xml_sitemap": "https://support.example.com/sitemap.xml",
      "description": "Support articles and troubleshooting guides",
      "freshness_days": 14
    }
  ]
}
```

### YAML Configuration Example

```yaml
websites:
  - name: Python Documentation
    xml_sitemap: https://docs.python.org/3/sitemap.xml
    description: Official Python programming language documentation
    freshness_days: 30
    exclude_patterns:
      - https://docs.python.org/3/archives/.*
    include_only_patterns:
      - https://docs.python.org/3/tutorial/.*

  - name: FastAPI Documentation
    xml_sitemap: https://fastapi.tiangolo.com/sitemap.xml
    description: Modern, fast web framework for building APIs
    freshness_days: 14
```

## Environment Variables

Set up your environment variables in the `.env` file. Here's a sample configuration:

```
# General Settings
DEBUG=true
LOG_LEVEL=INFO

# Authentication
ADMIN_PASSWORD=your_secure_password

# OpenAI API
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o

# Anthropic API (Optional)
ANTHROPIC_API_KEY=your_anthropic_api_key
ANTHROPIC_MODEL=claude-3-opus-20240229

# Vector Database
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=crawlnchat
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1

# Crawler Configuration
CRAWL_RATE_LIMIT=5  # Requests per second
CRAWL_TIMEOUT=30    # Seconds
MAX_RETRIES=3
USER_AGENT=CrawlnChat Bot/1.0

# Server Configuration
FASTAPI_PORT=8000
MCP_PORT=8001
HOST=0.0.0.0
```

## Usage

### Start the Service

```bash
# Start the full service (both frontends)
python -m src.main --config websites.json

# Start with specific frontend
python -m src.main --config websites.json --frontend fastapi
python -m src.main --config websites.json --frontend mcp

# Force recrawl of all websites
python -m src.main --config websites.json --recrawl

# Only crawl the websites without starting the servers
python -m src.main --config websites.json --crawl-only
```

### CLI Usage

The CLI interface allows for quick testing and interaction with the service:

```bash
# Query the system via CLI
python -m src.cli "What is the pricing model for the Basic plan?"

# Specify domain routing to target a specific website
python -m src.cli --namespace sales "What are the enterprise pricing options?"

# Get detailed debug information
python -m src.cli --debug "How do I reset my password?"
```

### API Endpoints

#### FastAPI Interface

The FastAPI server provides a comprehensive REST API with Swagger UI documentation:

- **Swagger UI**: http://localhost:8000/docs
- **Chat Endpoint**: `POST /api/chat`
  ```json
  {
    "message": "What are the main features of your product?",
    "namespace": "optional-specific-website-namespace"
  }
  ```
- **Websites Info**: `GET /api/websites`
- **Health Check**: `GET /api/health`

#### MCP (Model Context Protocol) Interface

For integration with Anthropic Claude and LangChain:

- **MCP Endpoint**: http://localhost:8001/
- Compatible with Anthropic's MCP specification

## Core Components

### Crawler Module

The crawler module handles fetching and processing website content from XML sitemaps:

```python
# src/crawler/processor.py
from src.crawler import process_websites

# Process websites from a configuration file
async def process_websites(config_path, force_recrawl=False):
    """
    Process websites defined in the configuration file.
    
    Args:
        config_path (str): Path to the configuration file (JSON or YAML)
        force_recrawl (bool): Whether to recrawl websites even if they exist in the DB
        
    Returns:
        dict: Summary of crawling results
    """
    # Load config, process sitemaps, fetch content, and store embeddings
    # ...
```

Key components:

- `SitemapParser`: Extracts URLs from XML sitemaps
- `AsyncContentFetcher`: Handles concurrent fetching with rate limiting
- `HtmlProcessor`: Converts HTML to markdown and cleans content

### Vector Storage

The vector storage system handles document chunking, embedding generation, and storage:

```python
# src/vector_store/pinecone.py
from src.vector_store import PineconeVectorStore, TextChunker

# Initialize vector store
store = PineconeVectorStore(
    index_name="crawlnchat",
    embedding_model="text-embedding-3-small"
)

# Chunk text into manageable segments
chunker = TextChunker(
    chunk_size=1000,
    chunk_overlap=200
)
chunks = chunker.chunk_text(
    text="Long markdown content...",
    metadata={"source": "https://example.com/page"}
)

# Store documents in vector database
store.add_documents(chunks, namespace="example-docs")

# Query for relevant documents
results = store.query(
    query="How do I reset my password?", 
    namespace="example-docs",
    limit=5
)
```

### Agent Framework

The system uses LangGraph to implement an agentic approach to routing and response generation:

```python
# src/core/router.py
from src.core.router import AgentRouter

# Initialize the agent router
router = AgentRouter(embedding_model="text-embedding-3-small")

# Process a user query
response = await router.process_query(
    query="What is your refund policy?",
    namespace=None  # None means search across all namespaces
)

# The response includes the answer and source attribution
print(response["answer"])  # The formatted answer
print(response["sources"])  # List of source URLs used
```

### Brand Review

Ensures responses comply with your brand guidelines:

```python
# src/core/brand_review.py
from src.core.brand_review import BrandReviewer

# Initialize with your brand guidelines
reviewer = BrandReviewer(guidelines_file="brand_guidelines.md")

# Review a draft response
result = reviewer.review(
    draft_response="The product costs $99 per month.",
    context="Pricing information request"
)

# Get the revised response
final_response = result["revised_response"]
print(f"Revised: {final_response}")
print(f"Changes made: {result['modification_summary']}")
```

## Logging System

The application includes comprehensive logging across all components:

```python
# src/core/logger.py
from src.core import get_logger

# Get a logger for a specific component
logger = get_logger("agent_router")

# Log with different severity levels
logger.debug("Processing query with parameters: %s", params)
logger.info("Successfully retrieved %d documents from vector store", len(docs))
logger.warning("Rate limit approaching, slowing down requests")
logger.error("Failed to connect to Pinecone: %s", str(error))
```

Log files are stored in the `logs/` directory, with rotation and formatting configured in `src/core/logger.py`.

## Project Structure

```
crawl-n-chat/
├── .env                  # Environment variables
├── .env.example          # Example environment variables
├── .gitignore            # Git ignore file
├── README.md             # This document
├── requirements.txt      # Python dependencies
├── websites.json         # Website configuration
├── brand_guidelines.md   # Guidelines for brand compliance
├── src/                  # Source code
│   ├── __init__.py       # Package initialization
│   ├── main.py           # Main application entry point
│   ├── cli.py            # Command line interface
│   ├── api/              # API frontend implementations
│   │   ├── __init__.py
│   │   ├── fastapi_app.py # FastAPI implementation
│   │   └── mcp_app.py    # MCP implementation
│   ├── core/             # Core functionality
│   │   ├── __init__.py
│   │   ├── settings.py   # Application settings
│   │   ├── logger.py     # Logging utilities
│   │   ├── router.py     # Query router
│   │   ├── agents.py     # LangGraph agent implementations
│   │   └── brand_review.py # Brand compliance checking
│   ├── crawler/          # Web crawling module
│   │   ├── __init__.py
│   │   ├── processor.py  # Website processing
│   │   ├── sitemap.py    # XML sitemap processing
│   │   └── fetcher.py    # Async content fetching
│   └── vector_store/     # Vector storage
│       ├── __init__.py
│       ├── base.py       # Base vector store interface
│       ├── chunker.py    # Text chunking
│       └── pinecone.py   # Pinecone implementation
└── logs/                 # Application logs
```

## Error Handling and Troubleshooting

The system implements robust error handling:

- **Crawler errors**: Failed URLs are logged and reported but don't stop the overall process
- **Database connection issues**: Automatic retries with exponential backoff
- **Rate limiting**: Built-in protection against exceeding API rate limits
- **Invalid queries**: Graceful handling with appropriate error messages

Common troubleshooting steps:

1. Check the logs in `logs/crawl-n-chat.log` for detailed error information
2. Verify your API keys in the `.env` file
3. Test connectivity to Pinecone using the health check API
4. Ensure your website configuration is valid JSON or YAML

## Advanced Configuration

### Custom Chunking Strategies

You can customize the chunking strategy in your environment variables:

```
# Chunking Configuration
CHUNK_SIZE=800
CHUNK_OVERLAP=150
CHUNK_TYPE=recursive  # Options: simple, recursive, semantic
```

### Multiple Embedding Models

The system supports configuring different embedding models:

```
# Default embedding model
DEFAULT_EMBEDDING_MODEL=text-embedding-3-small

# Alternate models (for specific websites)
ADVANCED_EMBEDDING_MODEL=text-embedding-3-large
```

### Custom Rate Limiting

Configure per-domain rate limiting in your website configuration:

```json
{
  "websites": [
    {
      "name": "Example Docs",
      "xml_sitemap": "https://example.com/sitemap.xml",
      "rate_limit": 10,  // Requests per second for this site
      "...": "..."
    }
  ]
}
```

## Roadmap

- [ ] Support for authentication and multi-user sessions
- [ ] Integration with Azure OpenAI
- [ ] Document-level permissions and access control
- [ ] Webhook support for real-time updates
- [ ] Web UI for administration and monitoring
- [ ] Support for additional vector databases (e.g., Qdrant, Milvus)
- [ ] Implement [langchain-mcp](https://github.com/langchain-ai/langchain-mcp-adapters)
- [ ] Docker containerization and Kubernetes support

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[MIT License](LICENSE)






