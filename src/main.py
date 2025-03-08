#!/usr/bin/env python3
"""
Main entry point for Crawl n Chat.

This module provides the main entry point for the application, handling command-line arguments
and coordinating the startup of various services.
"""
import argparse
import asyncio
import threading
import time  # Add time for sleep

import os
from typing import List

from src.core.settings import FASTAPI_PORT, MCP_PORT, DEFAULT_EMBEDDING_MODEL
from src.core.router import AgentRouter
from src.crawler import process_websites
from src.api import run_fastapi_server, run_mcp_server
from src.core import get_logger
from src.core.logger import configure_logging

logger = get_logger("main")

# Global state to track running servers
server_threads = []


def start_servers(frontends: List[str]) -> None:
    """
    Start the specified frontend servers in separate threads.

    Args:
        frontends: List of frontend types to start. Valid values are "fastapi", "mcp", or "all".
    """
    # Initialize shared services
    agent_router = AgentRouter(embedding_model=DEFAULT_EMBEDDING_MODEL)

    # Start FastAPI server if requested
    if "fastapi" in frontends or "all" in frontends:
        logger.info(f"Starting FastAPI server on port {FASTAPI_PORT}")
        fastapi_thread = threading.Thread(
            target=run_fastapi_server,
            args=(agent_router,),
            daemon=True,
        )
        server_threads.append(fastapi_thread)
        fastapi_thread.start()

    # Start MCP server if requested
    if "mcp" in frontends or "all" in frontends:
        logger.info(f"Starting MCP server on port {MCP_PORT}")
        mcp_thread = threading.Thread(
            target=run_mcp_server,
            args=(agent_router,),
            daemon=True,
        )
        mcp_thread.start()
        server_threads.append(mcp_thread)

    logger.info(f"Started {len(server_threads)} server(s)")


def main() -> None:
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="Crawl n Chat")
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the configuration file (JSON or YAML)",
    )
    parser.add_argument(
        "--recrawl",
        action="store_true",
        help="Recrawl websites even if they already exist in the vector database",
    )
    parser.add_argument(
        "--frontend",
        choices=["fastapi", "mcp", "all"],
        default="all",
        help="Frontend to run (default: all)",
    )
    parser.add_argument(
        "--crawl-only",
        action="store_true",
        help="Only crawl websites, don't start the servers",
    )
    parser.add_argument(
        "--debug",
        action="store_true", 
        help="Enable debug logging (default: error level logging)"
    )

    args = parser.parse_args()

    # Configure logging based on debug flag
    configure_logging("DEBUG" if args.debug else "ERROR")
    
    if args.debug:
        logger.debug("Debug logging enabled")

    # Process websites
    asyncio.run(process_websites(args.config, args.recrawl))

    # Start servers unless --crawl-only is specified
    if not args.crawl_only:
        frontends = [args.frontend]
        if args.frontend == "all":
            frontends = ["fastapi", "mcp"]
            
        start_servers(frontends)

        # Keep main thread running to avoid shutting down too early
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down servers...")


if __name__ == "__main__":
    main()
