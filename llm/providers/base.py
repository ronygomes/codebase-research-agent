from abc import ABC, abstractmethod

from llm.types import LLMResponse, Message, ToolDefinition


class LLMProvider(ABC):
    @abstractmethod
    def chat(
        self,
        system_prompt: str,
        messages: list[Message],
        tools: list[ToolDefinition],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse: ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...
