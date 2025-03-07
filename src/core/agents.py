"""
Agent logic for Crawl n Chat.

This module implements the core agent logic for processing user queries,
retrieving relevant information, and generating responses while maintaining
brand compliance.
"""

from typing import List, Tuple, TypedDict, Dict, Any
import json
from langchain_core.messages import ToolMessage, AIMessage, BaseMessage
from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain_core.tools import tool
from langchain_core.language_models import BaseLanguageModel
from core.logger import get_logger
from core.brand_review import BrandReviewer
from core.settings import DEFAULT_ANSWER, NUM_RAG_SOURCES
from pydantic import BaseModel, Field

logger = get_logger("agent_logic")


class AgentState(TypedDict):
    """
    Represents the current state of the agent's processing.
    """

    question: str
    messages: List[BaseMessage]
    context: str
    answer: str
    final_answer: str
    sources: List[str]
    error: str


class AnswerResponse(BaseModel):
    """
    Structured response format for agent answers.
    """

    response: str = Field(..., description="Detailed answer to the user's question.")
    sources: List[str] = Field(
        ...,
        description="List of sources used to generate the answer, as complete URLs.",
    )


class AgentLogic:
    """
    Core agent logic for processing queries and generating responses.

    This class handles the orchestration of:
    - Tool selection and execution
    - Context retrieval
    - Answer generation
    - Brand compliance review
    """

    def __init__(
        self, llm: BaseLanguageModel, vector_store: Any, websites: List[Dict[str, str]]
    ) -> None:
        """
        Initialize the agent logic.

        Args:
            llm: Language model for generating responses
            vector_store: Vector store for retrieving relevant context
            websites: List of website configurations to process
        """
        self.llm = llm
        self.vector_store = vector_store
        self.websites = websites
        self.brand_reviewer = BrandReviewer(self.llm)
        logger.info(f"Initializing AgentLogic with {len(websites)} websites")
        self.retrieval_tools = self._create_website_retrieval_tools()
        logger.info(f"Created {len(self.retrieval_tools)} retrieval tools")
        self.llm_with_tools = self.llm.bind_tools(self.retrieval_tools)
        self.structured_llm = self.llm.with_structured_output(AnswerResponse)

    def _create_website_retrieval_tools(self) -> List[Any]:
        """
        Create retrieval tools for each configured website.

        Returns:
            List of tool functions for retrieving information from each website
        """
        tools = []
        for website in self.websites:
            namespace = website["name"].lower().replace(" ", "_")
            description = website["description"]
            tool_name = f"retrieve_from_{namespace}"
            logger.info(f"Creating retrieval tool: {tool_name}")

            @tool(tool_name, description=description)
            def retrieval_tool(
                query: str, namespace: str = namespace
            ) -> Dict[str, Any]:
                """
                Retrieve relevant information from a specific website namespace.

                Args:
                    query: The search query
                    namespace: The website namespace to search in

                Returns:
                    Dict containing retrieved context and source URLs
                """
                logger.info(
                    f"Executing retrieval tool for {namespace} with query: '{query[:50]}...'"
                )
                context, sources = self._retrieval_tool(query, namespace)
                return {"context": context, "sources": sources}

            tools.append(retrieval_tool)

        return tools

    def _retrieval_tool(self, query: str, namespace: str) -> Tuple[str, List[str]]:
        """
        Retrieve information from the vector store for a specific namespace.

        Args:
            query: The search query
            namespace: The website namespace to search in

        Returns:
            Tuple of (context string, list of source URLs)
        """
        logger.info(f"Retrieving {NUM_RAG_SOURCES} sources from {namespace}")

        try:
            results = self.vector_store.query(
                query_text=query, namespace=namespace, top_k=NUM_RAG_SOURCES
            )

            context = f"Information from {namespace}:\n\n"
            sources = [
                result.get("metadata", {}).get("source", "") for result in results
            ]
            context += "\n\n".join(
                [
                    f"Document {src}:\n{res['text']}"
                    for src, res in zip(sources, results)
                ]
            )

            # Remove duplicates while preserving order
            sources = list(dict.fromkeys(sources))

            logger.info(f"Retrieved {len(sources)} unique sources from {namespace}")

            return context, sources

        except Exception as e:
            logger.error(f"Error retrieving from {namespace}: {e}")
            return f"Error retrieving information from {namespace}: {str(e)}", []

    async def agent_node(self, state: AgentState) -> AgentState:
        """
        Process the agent's messages and coordinate the response generation.

        Args:
            state: Current agent state

        Returns:
            Updated agent state
        """
        logger.info("Agent node started")

        messages = state["messages"]
        try:
            if messages and isinstance(messages[-1], ToolMessage):
                logger.info("Processing tool results to generate response")
                return await self._process_tool_result(state)

            if state.get("answer"):
                logger.info("Already have an answer, routing to review")
                return state

            logger.info("Deciding which tool to use")
            return await self._invoke_llm_with_tools(state)

        except Exception as e:
            logger.error(f"Error in agent node: {e}")
            state["error"] = f"Error in agent node: {str(e)}"

        return state

    async def _invoke_llm_with_tools(self, state: AgentState) -> AgentState:
        """
        Invoke the LLM with available tools to process the query.

        Args:
            state: Current agent state

        Returns:
            Updated agent state
        """
        try:
            logger.info("Invoking LLM with tools to decide next action")
            response = await self.llm_with_tools.ainvoke(state["messages"])
            state["messages"].append(response)

            if hasattr(response, "tool_calls") and response.tool_calls:
                logger.info(
                    f"Agent generated tool call: {response.tool_calls[0]['name'] if response.tool_calls else 'None'}"
                )
                state["answer"] = None
            else:
                logger.info("Agent generated a direct response without using tools")
                state["answer"] = response.content
                state["sources"] = []

        except Exception as e:
            logger.error(f"Error invoking LLM with tools: {e}")
            state["error"] = f"Error invoking LLM with tools: {str(e)}"

        return state

    async def _process_tool_result(self, state: AgentState) -> AgentState:
        """
        Process the results from tool execution.

        Args:
            state: Current agent state

        Returns:
            Updated agent state with processed tool results
        """
        try:
            logger.info("Processing tool result")
            tool_result = json.loads(state["messages"][-1].content)
            state["context"] = tool_result.get("context", "")

            raw_sources = tool_result.get("sources", [])
            state["sources"] = raw_sources

            logger.info(f"Tool executed with {len(raw_sources)} sources")

            state = await self._generate_answer_response(state)

            if state.get("answer"):
                state["messages"].append(AIMessage(content=state["answer"]))
                logger.info("Added answer to messages")

        except Exception as e:
            logger.error(f"Error processing tool result: {e}")
            state["error"] = f"Error processing tool result: {str(e)}"

        return state

    async def _generate_answer_response(self, state: AgentState) -> AgentState:
        """
        Generate a structured answer response using the LLM.

        Args:
            state: Current agent state

        Returns:
            Updated agent state with generated answer
        """
        logger.info("Generating structured answer response")

        raw_sources = state.get("sources", [])

        prompt_args = {
            "context": state["context"],
            "question": state["question"],
            "sources": ", ".join(state["sources"]),
        }

        messages = self._create_answer_response_prompt().format_messages(**prompt_args)

        try:
            logger.info("Invoking structured LLM to generate response")
            structured_output = await self.structured_llm.ainvoke(messages)

            state["answer"] = structured_output.response
            state["final_answer"] = structured_output.response
            state["sources"] = structured_output.sources

            logger.info(
                f"Generated structured response with {len(structured_output.sources)} sources"
            )

        except Exception as e:
            logger.error(f"Error generating structured output: {e}")
            logger.info("Falling back to simple response")
            fallback_response = await self.llm.ainvoke(messages)
            state["answer"] = fallback_response.content
            state["final_answer"] = fallback_response.content
            state["sources"] = raw_sources

        return state

    def _create_answer_response_prompt(self) -> ChatPromptTemplate:
        """
        Create the prompt template for generating answer responses.

        Returns:
            ChatPromptTemplate configured for answer generation
        """
        prompt_template = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(
                    "You are a helpful assistant that generates detailed answers based on provided context. "
                    "Your response should be accurate, concise, and directly address the user's question. "
                    "Include relevant sources as complete URLs exactly as provided, without modifying them."
                ),
                HumanMessagePromptTemplate.from_template(
                    "Given the following context, answer the user's question.\n\n"
                    "Context:\n{context}\n\n"
                    "Question:\n{question}\n\n"
                    "Sources available:\n{sources}\n\n"
                    "IMPORTANT: For sources, return the complete URLs exactly as provided. "
                    "Do not modify, split, or change the URLs in any way."
                ),
            ]
        )

        return prompt_template

    async def review_node(self, state: AgentState) -> AgentState:
        """
        Review the generated answer for brand compliance.

        Args:
            state: Current agent state

        Returns:
            Updated agent state with reviewed answer
        """
        logger.info("Reviewing answer for brand compliance")

        if not state.get("answer"):
            logger.warning("No answer to review")
            state["final_answer"] = DEFAULT_ANSWER
            state["sources"] = []
            return state

        try:
            if self.brand_reviewer:
                reviewed_answer = self.brand_reviewer.review(state["answer"])
                if reviewed_answer:
                    state["final_answer"] = reviewed_answer
                    logger.info("Answer reviewed and updated for brand compliance")
            else:
                state["final_answer"] = state["answer"]
                logger.info("No brand reviewer configured, using original answer")

        except Exception as e:
            logger.error(f"Error in review node: {e}")
            state["error"] = f"Error in review node: {str(e)}"
            state["final_answer"] = state["answer"]  # Fall back to original answer

        return state

    def should_use_tools(self, state: AgentState) -> str:
        """Determine if tools should be used based on the last message."""

        last_message = state["messages"][-1]
        route_decision = (
            "tools"
            if hasattr(last_message, "tool_calls") and last_message.tool_calls
            else "review"
        )

        logger.info(f"Routing decision: {route_decision}")
        return route_decision
