#!/usr/bin/env python3
"""
Command-line interface for Crawl n Chat.
"""
import argparse
import asyncio
from typing import Optional, List

from src.core.router import AgentRouter
from src.core.settings import DEFAULT_EMBEDDING_MODEL
from src.core.logger import get_logger, configure_logging

logger = get_logger("cli")


async def ask_question(query: str) -> None:
    """
    Ask a question via the CLI.

    Args:
        query: The question to ask.
    """
    try:
        # Initialize the agent router
        agent_router = AgentRouter(embedding_model=DEFAULT_EMBEDDING_MODEL)

        # Process the query
        result = await agent_router.process_query(query=query)

        # Print the response
        print("\n" + "-" * 80)
        print(f"Query: {query}")

        # Handle sources display
        sources = result.get("sources", [])
        if sources:
            print("Sources used:")
            for source in sources:
                print(f"- {source}")
        else:
            print("No sources used")

        print("-" * 80)
        print(result["response"])
        print("-" * 80 + "\n")

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        print(f"Error: {str(e)}")


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="Crawl n Chat CLI")

    parser.add_argument(
        "query",
        nargs="?",
        help="The question to ask (if not provided, will prompt for input)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging (default: error level logging)"
    )

    args = parser.parse_args()

    if args.debug:
        configure_logging("DEBUG")
        logger.debug("Debug logging enabled")

    # Get query from argument or prompt
    query = args.query
    if not query:
        query = input("Enter your question: ")

    # Run the async function
    asyncio.run(ask_question(query=query))


if __name__ == "__main__":
    main()
