"""
FastAPI interface for Crawl n Chat.

This module provides the FastAPI web server implementation for the Crawl n Chat service.
It handles:
- API endpoint definitions
- Request/response models
- Server lifecycle management
- Error handling
"""

from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import time


from src.core.settings import (
    FASTAPI_PORT,
    SERVER_URL,
    API_TITLE,
    API_DESCRIPTION,
    API_VERSION,
    DEFAULT_EMBEDDING_MODEL,
)
from src.core.router import AgentRouter
from src.core import get_logger


logger = get_logger("fastapi_app")

# Global service instances
agent_router: Optional[AgentRouter] = None


app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    docs_url="/docs",
    servers=[{"url": SERVER_URL}],
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RootResponse(BaseModel):
    """
    Response model for the root endpoint.

    Attributes:
        message: A welcome message for the API
    """
    message: str = "Welcome to Crawl n Chat API"


class ChatRequest(BaseModel):
    """
    Request model for the chat endpoint.

    Attributes:
        query: The user's question or message to process
    """

    query: str = Field(
        ..., description="The user query to process", min_length=1, max_length=1000
    )


class ChatResponse(BaseModel):
    """
    Response model for the chat endpoint.

    Attributes:
        response: The AI-generated response to the user's query
        sources: List of source URLs that were used to generate the response
    """

    response: str = Field(
        ..., description="The AI-generated response to the user's query"
    )
    sources: List[str] = Field(
        ..., description="List of source URLs that provided information for the answer"
    )



@app.get("/", response_model=RootResponse)
async def root() -> Dict[str, str]:
    """
    Root endpoint that provides a basic welcome message.

    Returns:
        Dict[str, str]: A simple welcome message.
    """
    return {"message": "Welcome to Crawl n Chat API"}


@app.post("/chat", 
          response_model=ChatResponse,
          description="Process a chat request and generate a response based on website content. Returns AI-generated answer with source information.")
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Process a chat request and generate a response.

    This endpoint:
    1. Validates the incoming request
    2. Processes the query using the agent router
    3. Returns the AI-generated response with sources

    Args:
        request: The chat request containing the query and optional parameters.

    Returns:
        ChatResponse: The AI-generated response with source information.

    Raises:
        HTTPException(503): If the service is not properly initialized.
        HTTPException(500): If an error occurs while processing the request.
    """
    global agent_router

    if not agent_router:
        raise HTTPException(
            status_code=503,
            detail="Service not initialized. Please try again in a few moments.",
        )

    try:
        # Process the query using the pre-initialized router
        start_time = time.time()
        result = await agent_router.process_query(query=request.query)
        process_time = time.time() - start_time
        logger.info(f"Query processed in {process_time:.2f} seconds")

        return ChatResponse(
            response=result["response"], sources=result.get("sources", [])
        )
    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing your request: {str(e)}",
        )


def run_fastapi_server(
    init_agent_router: AgentRouter = None,
) -> None:
    """
    Start the FastAPI server.

    Args:
        init_agent_router: AgentRouter instance to use.

    Note:
        This function blocks until the server is shut down.
    """
    global agent_router

    agent_router = (
        init_agent_router
        if init_agent_router
        else AgentRouter(embedding_model=DEFAULT_EMBEDDING_MODEL)
    )

    if not agent_router:
        raise RuntimeError("Agent router not initialized before starting the server")

    # Run with uvicorn directly instead of using Server class
    logger.info(f"Starting FastAPI server on port {FASTAPI_PORT}")
    logger.info(f"✅ FastAPI server is ready - API available at http://localhost:{FASTAPI_PORT}")
    logger.info(f"📝 API documentation available at http://localhost:{FASTAPI_PORT}/docs")
    uvicorn.run(
        app, host="0.0.0.0", port=FASTAPI_PORT, log_config=None, log_level="info"
    )


if __name__ == "__main__":
    run_fastapi_server()
