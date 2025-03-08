"""
Brand compliance review utility for Crawl n Chat.
"""

from typing import Dict, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage

from src.core.settings import DEFAULT_ANSWER, BRAND_GUIDELINES_FILE
from src.core.logger import get_logger

logger = get_logger("brand_review")


class BrandReviewer:
    """
    Reviewer that checks AI responses against brand guidelines.

    This class ensures that AI-generated responses comply with specified brand guidelines.
    It can load guidelines from a file or use default guidelines if none are provided.
    The reviewer makes minimal necessary changes to align responses with guidelines
    and falls back to a default answer if compliance cannot be achieved.

    Attributes:
        llm: The language model used for reviewing responses.
        guidelines: The brand guidelines text used for review.
    """

    def __init__(self, llm: BaseChatModel):
        """
        Initialize the brand reviewer.

        Args:
            llm: The language model to use for review.
        """
        self.llm: BaseChatModel = llm
        self.guidelines: str = ""

        # Load guidelines
        if isinstance(BRAND_GUIDELINES_FILE, str) and BRAND_GUIDELINES_FILE:
            try:
                with open(BRAND_GUIDELINES_FILE, "r") as f:
                    self.guidelines = f.read()
            except Exception as e:
                logger.error(f"Error loading brand guidelines file: {e}")
                self.guidelines = ""
        else:
            self.guidelines = """
            General brand guidelines:
            - Be helpful, clear, and concise
            - Maintain a professional but friendly tone
            - Avoid excessive jargon
            - Respect user privacy
            - Don't make claims that cannot be substantiated
            - Don't promise features or functionality not offered
            - Always be accurate and truthful
            """
            logger.warning("No specific brand guidelines provided, using defaults")

    def review(self, response: str) -> str:
        """
        Review a response against brand guidelines.

        Args:
            response: The AI response to review.

        Returns:
            str: A revised response string that complies with brand guidelines.
                 If the response cannot be made compliant, returns the default answer.

        Note:
            If the review process fails or the response cannot be made compliant,
            this method will return the default answer defined in settings.
        """
        try:
            prompt = f"""
            # Brand Guidelines
            {self.guidelines}
            
            # Task
            Review the following AI response against our brand guidelines.
            Make minimal changes necessary to align with our guidelines.
            
            # Response to Review
            {response}
            
            # Instructions
            1. Evaluate if the response follows the brand guidelines.
            2. If compliant, return it unchanged.
            3. If revision is needed, make minimal edits to align it with guidelines.
            4. If unable to revise adequately, clearly state "<unanswerable>".
            
            # Output Format
            Return ONLY the revised response text or the fallback message.
            """

            result = self.llm.invoke([HumanMessage(content=prompt)])
            reviewed_response = result.content.strip()

            if reviewed_response.lower() == "<unanswerable>".lower():
                logger.info("Brand review unable to revise response adequately.")
                return DEFAULT_ANSWER

            return reviewed_response

        except Exception as e:
            logger.error(f"Error during brand review: {e}")
            return DEFAULT_ANSWER
