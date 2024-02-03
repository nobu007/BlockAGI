from typing import List

from langchain.prompts import ChatPromptTemplate
from langchain.schema import BaseMessage


def pretty_prompt(messages: List[BaseMessage]) -> str:
    """Return pretty prompt."""
    return ChatPromptTemplate.from_messages(messages).format()
