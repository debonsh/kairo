"""Multi-provider LLM client with fallback chain.
Routes to: Ollama > Groq > CommandCode > DeepSeek > OpenAI.
All providers unified under one interface. Switching is config-driven."""

import os
import json
from dataclasses import dataclass
from loguru import logger


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    parsed: dict | None = None


class LLMClient:
    def __init__(self, provider: str | None = None):
        self.provider = provider or os.getenv("LLM_REALTIME_PROVIDER", "ollama")
        self.research_provider = os.getenv("LLM_RESEARCH_PROVIDER", "commandcode")

        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen3:8b")
        self.ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        self.commandcode_key = os.getenv("COMMANDCODE_API_KEY", "")
        self.commandcode_base = os.getenv("COMMANDCODE_BASE_URL", "https://api.commandcode.ai/v1")
        self.commandcode_model = os.getenv("COMMANDCODE_MODEL", "deepseek-v4-pro")

        self.deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.groq_key = os.getenv("GROQ_API_KEY", "")

        self._ollama_client = None
        self._openai_client = None

    def ask(self, prompt: str, system: str = "", temperature: float = 0.3,
            max_tokens: int = 512, provider: str | None = None) -> LLMResponse:
        provider_use = provider or self.provider

        if provider_use == "ollama":
            return self._ask_ollama(prompt, system, temperature, max_tokens)
        elif provider_use == "commandcode":
            return self._ask_commandcode(prompt, system, temperature, max_tokens)
        elif provider_use == "deepseek":
            return self._ask_deepseek(prompt, system, temperature, max_tokens)
        elif provider_use == "openai":
            return self._ask_openai(prompt, system, temperature, max_tokens)
        elif provider_use == "groq":
            return self._ask_groq(prompt, system, temperature, max_tokens)
        else:
            logger.warning(f"Unknown provider: {provider_use}, falling back to ollama")
            return self._ask_ollama(prompt, system, temperature, max_tokens)

    def ask_with_fallback(self, prompt: str, system: str = "", temperature: float = 0.3,
                          max_tokens: int = 512) -> LLMResponse:
        providers = ["ollama", "groq", "commandcode", "deepseek", "openai"]
        last_error = None
        for provider in providers:
            try:
                return self.ask(prompt, system, temperature, max_tokens, provider=provider)
            except Exception as e:
                last_error = e
                logger.warning(f"Provider {provider} failed: {e}")

        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

    def _ask_ollama(self, prompt: str, system: str, temperature: float, max_tokens: int) -> LLMResponse:
        import time
        start = time.time()

        from ollama import Client
        if not self._ollama_client:
            self._ollama_client = Client(host=self.ollama_base)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # qwen3-style thinking models burn tokens on reasoning before the real
        # answer — give them room so content isn't empty. `think: False` reduces
        # (but doesn't eliminate) thinking; the larger budget guarantees output.
        response = self._ollama_client.chat(
            model=self.ollama_model,
            messages=messages,
            options={
                "temperature": temperature,
                "num_predict": max(1024, max_tokens * 2),
                "think": False,
            },
        )

        latency = int((time.time() - start) * 1000)
        text = self._ollama_content(response)
        parsed = self._try_parse_json(text)

        return LLMResponse(
            text=text,
            provider="ollama",
            model=self.ollama_model,
            tokens_in=self._ollama_field(response, "prompt_eval_count", 0),
            tokens_out=self._ollama_field(response, "eval_count", 0),
            latency_ms=latency,
            parsed=parsed,
        )

    @staticmethod
    def _ollama_content(response) -> str:
        """Extract assistant content — ollama returns a ChatResponse object
        (newer client versions), but older versions returned a dict."""
        message = response.get("message") if isinstance(response, dict) else getattr(response, "message", None)
        if message is None:
            return ""
        return message.get("content", "") if isinstance(message, dict) else getattr(message, "content", "")

    @staticmethod
    def _ollama_field(response, key: str, default=0):
        if isinstance(response, dict):
            return response.get(key, default)
        return getattr(response, key, default)

    def _ask_deepseek(self, prompt: str, system: str, temperature: float, max_tokens: int) -> LLMResponse:
        return self._openai_compatible("deepseek", prompt, system, temperature, max_tokens,
                                       api_key=self.deepseek_key,
                                       base_url="https://api.deepseek.com/v1")

    def _ask_commandcode(self, prompt: str, system: str, temperature: float, max_tokens: int) -> LLMResponse:
        return self._openai_compatible("commandcode", prompt, system, temperature, max_tokens,
                                       api_key=self.commandcode_key,
                                       base_url=self.commandcode_base,
                                       model=self.commandcode_model)

    def _ask_groq(self, prompt: str, system: str, temperature: float, max_tokens: int) -> LLMResponse:
        return self._openai_compatible("groq", prompt, system, temperature, max_tokens,
                                       api_key=self.groq_key,
                                       base_url="https://api.groq.com/openai/v1",
                                       model="llama-3.1-8b-instant")

    def _ask_openai(self, prompt: str, system: str, temperature: float, max_tokens: int) -> LLMResponse:
        return self._openai_compatible("openai", prompt, system, temperature, max_tokens,
                                       api_key=self.openai_key,
                                       model="gpt-4o-mini")

    def _openai_compatible(self, provider: str, prompt: str, system: str,
                           temperature: float, max_tokens: int, api_key: str,
                           base_url: str = "https://api.openai.com/v1",
                           model: str | None = None) -> LLMResponse:
        import time
        if not api_key:
            raise RuntimeError(f"No API key for {provider}")
        start = time.time()

        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        model_name = model or ("gpt-4o-mini" if provider == "openai" else
                               "deepseek-v4" if provider == "deepseek" else
                               "deepseek-v4-pro" if provider == "commandcode" else
                               "llama-3.1-8b-instant")

        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        latency = int((time.time() - start) * 1000)
        content = response.choices[0].message.content
        parsed = self._try_parse_json(content)

        return LLMResponse(
            text=content,
            provider=provider,
            model=model_name,
            tokens_in=response.usage.prompt_tokens,
            tokens_out=response.usage.completion_tokens,
            latency_ms=latency,
            parsed=parsed,
        )

    def _try_parse_json(self, text: str) -> dict | None:
        try:
            text = text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text)
        except (json.JSONDecodeError, IndexError):
            return None

    def structured_prompt(self, prompt: str, output_format: str) -> str:
        return f"{prompt}\n\n{output_format}"
