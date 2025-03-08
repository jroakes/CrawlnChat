"""
Agent router module for Crawl n Chat using LangGraph for an agentic framework.
"""

from typing import Dict, Optional, Any
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from src.core.settings import (
    DEFAULT_LLM_MODEL,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_ANSWER,
    load_website_configs,
)
from src.vector_store.pinecone import PineconeWebsiteVectorStore
from src.core.logger import get_logger
from src.core.agents import AgentLogic, AgentState

logger = get_logger("agent_router")


SYSTEM_PROMPT = """
You are a helpful assistant that generates detailed answers based on provided context. 
Your response should be accurate, concise, and directly address the user's question. 
You must use one of the provided tools, when available, to answer the question. 
It is critial that all answers are based on the information provided by the tools.
"""


class AgentRouter:
    """
    Routes questions to appropriate RAG tools and generates responses using LangGraph.

    This agent uses an agentic approach to:
    1. Process a user query
    2. Choose which website's knowledge to query based on the question
    3. Retrieve context from the selected vector store namespace
    4. Generate a response based on retrieved context
    5. Review the response for brand compliance
    """

    def __init__(
        self,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        llm_model: str = DEFAULT_LLM_MODEL,
        config_file: Optional[str] = None,
    ):
        """
        Initialize the agent router.

        Args:
            embedding_model: Name of the embedding model.
            llm_model: Name of the LLM model for response generation.
            config_file: Path to websites configuration file (JSON or YAML).
        """
        self.vector_store = PineconeWebsiteVectorStore(embedding_model=embedding_model)
        self.llm_model = llm_model
        self.llm = self.create_llm(llm_model)
        self.websites = load_website_configs(config_file)
        self.agent_logic = AgentLogic(self.llm, self.vector_store, self.websites)
        self.workflow = self._setup_agent_workflow()

    @staticmethod
    def create_llm(llm_model) -> ChatOpenAI:
        return ChatOpenAI(model=llm_model)

    def _setup_agent_workflow(self) -> StateGraph:
        """
        Set up the LangGraph agent workflow.

        Returns:
            StateGraph: The configured agent workflow.
        """
        workflow = StateGraph(AgentState)
        workflow.add_node("tools", ToolNode(self.agent_logic.retrieval_tools))
        workflow.add_node("agent", self.agent_logic.agent_node)
        workflow.add_node("review", self.agent_logic.review_node)
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges(
            "agent",
            self.agent_logic.should_use_tools,
            {"tools": "tools", "review": "review"},
        )
        workflow.add_edge("tools", "agent")
        workflow.add_edge("review", END)
        return workflow.compile(debug=False)

    async def process_query(self, query: str) -> Dict[str, Any]:
        """
        Process a user query through the agent workflow.

        Args:
            query: The user's query.

        Returns:
            Dictionary with response, sources, and optional workflow trace.
        """
        try:
            logger.info(f"Processing query: '{query}'")

            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=query),
            ]

            # Set up the initial state
            initial_state: AgentState = {
                "question": query,
                "messages": messages,
                "context": None,
                "answer": None,
                "final_answer": None,
                "sources": [],
                "error": None,
            }

            logger.info(f"Starting workflow for query: '{query}'")

            # Run the workflow
            final_state = await self.workflow.ainvoke(initial_state)

            # Log completion status
            if final_state.get("error"):
                logger.error(f"Workflow ended with error: {final_state['error']}")
            elif not final_state.get("final_answer"):
                logger.error("Workflow ended without a final answer")
            else:
                logger.info("Workflow completed successfully")

            # Ensure sources is a proper list of strings
            sources = final_state.get("sources", ["No sources found"])

            # Return the final answer and sources from the agent state
            result = {
                "response": final_state.get("final_answer", DEFAULT_ANSWER),
                "sources": sources,
            }

            return result

        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return {
                "response": "I'm sorry, I encountered an error while processing your question. Please try again later.",
                "sources": [],
                "error": str(e),
            }
