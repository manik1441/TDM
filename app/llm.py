"""
Unified LLM client for TDM.
Uses the OpenAI Python library with a custom base_url to support OpenRouter
and any other OpenAI-compatible provider (local Ollama, direct OpenAI, Anthropic, etc.).
"""

from functools import lru_cache
from pathlib import Path
from openai import OpenAI
from app.config import get_llm_config
from app.logger import get_logger

logger = get_logger(__name__)


class LLMClient:
    """
    Thin wrapper around the OpenAI client configured for OpenRouter.
    Supports chat completions with optional JSON mode.
    """

    def __init__(self):
        config = get_llm_config()

        if not config["api_key"]:
            raise ValueError(
                "OPENROUTER_API_KEY is not set. "
                "Copy .env.example to .env and add your API key."
            )

        self._client = OpenAI(
            api_key=config["api_key"],
            base_url=config["base_url"],
        )
        self._model = config["model"]
        self._temperature = config["temperature"]
        self._max_tokens = config["max_tokens"]

        logger.info(f"LLM client initialized — provider={config['provider']}, model={self._model}")

    def chat(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        """
        Send a chat completion request and return the assistant's message content.

        Args:
            messages: List of {"role": "system"|"user"|"assistant", "content": "..."} dicts.
            temperature: Override default temperature for this call.
            max_tokens: Override default max_tokens for this call.
            json_mode: If True, request JSON output format.

        Returns:
            The text content of the assistant's response.
        """
        kwargs = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self._temperature,
            "max_tokens": max_tokens if max_tokens is not None else self._max_tokens,
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        logger.info(f"LLM request — model={self._model}, messages={len(messages)}, json_mode={json_mode}")

        try:
            response = self._client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            logger.info(f"LLM response — tokens_used={response.usage.total_tokens if response.usage else 'N/A'}")
            return content
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            raise

    def health_check(self) -> dict:
        """
        Quick connectivity test. Returns status dict.
        """
        try:
            response = self.chat(
                messages=[{"role": "user", "content": "Respond with exactly: OK"}],
                max_tokens=5,
            )
            return {"status": "connected", "model": self._model, "response": response.strip()}
        except Exception as e:
            return {"status": "error", "model": self._model, "error": str(e)}


# Module-level singleton — lazy initialized
_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Returns the singleton LLM client instance."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


PROMPTS_DIR = Path(__file__).parent.parent / "agents"


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    """Return a prompt markdown file by stem or filename."""
    filename = name if name.endswith(".md") else f"{name}.md"
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def run_markdown_agent(
    prompt_name: str,
    user_content: str,
    *,
    json_mode: bool = False,
    temperature: float = 0.1,
    max_tokens: int | None = None,
) -> str:
    """Run an LLM call whose system instructions live in the agents directory."""
    client = get_llm_client()
    return client.chat(
        messages=[
            {"role": "system", "content": load_prompt(prompt_name)},
            {"role": "user", "content": user_content},
        ],
        json_mode=json_mode,
        temperature=temperature,
        max_tokens=max_tokens,
    )
