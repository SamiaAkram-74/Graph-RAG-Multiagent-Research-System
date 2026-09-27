# """
# LLM abstraction layer.
# Provides a unified interface to Gemini and OpenAI models.
# """

# from __future__ import annotations

# from typing import Optional

# from loguru import logger

# from src.config import get_settings


# class LLMClient:
#     """Unified LLM client that wraps Gemini and OpenAI."""

#     def __init__(self, provider: Optional[str] = None):
#         self.settings = get_settings()
#         self.provider = provider or self.settings.LLM_PROVIDER
#         self._client = None
#         self._model_name = ""
#         self._init_client()

#     def _init_client(self) -> None:
#         if self.provider == "gemini":
#             import google.generativeai as genai
#             genai.configure(api_key=self.settings.GEMINI_API_KEY)
#             self._client = genai
#             self._model_name = self.settings.GEMINI_MODEL
#             logger.info(f"LLM initialised: Gemini ({self._model_name})")
#         elif self.provider == "openai":
#             from openai import OpenAI
#             self._client = OpenAI(api_key=self.settings.OPENAI_API_KEY)
#             self._model_name = self.settings.OPENAI_MODEL
#             logger.info(f"LLM initialised: OpenAI ({self._model_name})")
#         else:
#             raise ValueError(f"Unsupported LLM provider: {self.provider}")

#     def generate(
#         self,
#         prompt: str,
#         system_prompt: str = "",
#         temperature: Optional[float] = None,
#         max_tokens: int = 4096,
#     ) -> str:
#         """Generate a completion from the LLM."""
#         temp = temperature if temperature is not None else self.settings.TEMPERATURE

#         if self.provider == "gemini":
#             return self._generate_gemini(prompt, system_prompt, temp, max_tokens)
#         elif self.provider == "openai":
#             return self._generate_openai(prompt, system_prompt, temp, max_tokens)
#         raise RuntimeError("No valid LLM provider configured")

#     def _generate_gemini(
#         self, prompt: str, system_prompt: str, temperature: float, max_tokens: int
#     ) -> str:
#         model = self._client.GenerativeModel(
#             self._model_name,
#             system_instruction=system_prompt if system_prompt else None,
#         )
#         generation_config = {
#             "temperature": temperature,
#             "max_output_tokens": max_tokens,
#         }
#         response = model.generate_content(
#             prompt,
#             generation_config=generation_config,
#         )
#         return response.text

#     def _generate_openai(
#         self, prompt: str, system_prompt: str, temperature: float, max_tokens: int
#     ) -> str:
#         messages = []
#         if system_prompt:
#             messages.append({"role": "system", "content": system_prompt})
#         messages.append({"role": "user", "content": prompt})

#         response = self._client.chat.completions.create(
#             model=self._model_name,
#             messages=messages,
#             temperature=temperature,
#             max_tokens=max_tokens,
#         )
#         return response.choices[0].message.content

#     def count_tokens(self, text: str) -> int:
#         """Approximate token count for the text."""
#         try:
#             import tiktoken
#             enc = tiktoken.encoding_for_model("gpt-4")
#             return len(enc.encode(text))
#         except Exception:
#             # Fallback: rough estimate
#             return len(text.split()) * 4 // 3


# def get_llm(provider: Optional[str] = None) -> LLMClient:
#     """Factory function to get an LLM client."""
#     return LLMClient(provider=provider)

"""
LLM abstraction layer.
Provides a unified interface to Gemini and OpenAI models.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

from src.config import get_settings


class LLMClient:
    """Unified LLM client that wraps Gemini and OpenAI."""

    def __init__(self, provider: Optional[str] = None):
        self.settings = get_settings()
        self.provider = provider or self.settings.LLM_PROVIDER
        self._client = None
        self._model_name = ""
        self._init_client()

    def _init_client(self) -> None:
        if self.provider == "gemini":
            from google import genai

            self._client = genai.Client(
                api_key=self.settings.GEMINI_API_KEY
            )

            self._model_name = self.settings.GEMINI_MODEL

            logger.info(
                f"LLM initialised: Gemini ({self._model_name})"
            )

        elif self.provider == "openai":
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.settings.OPENAI_API_KEY
            )

            self._model_name = self.settings.OPENAI_MODEL

            logger.info(
                f"LLM initialised: OpenAI ({self._model_name})"
            )

        else:
            raise ValueError(
                f"Unsupported LLM provider: {self.provider}"
            )

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
    ) -> str:
        """Generate a completion from the LLM."""

        temp = (
            temperature
            if temperature is not None
            else self.settings.TEMPERATURE
        )

        if self.provider == "gemini":
            return self._generate_gemini(
                prompt,
                system_prompt,
                temp,
                max_tokens,
            )

        elif self.provider == "openai":
            return self._generate_openai(
                prompt,
                system_prompt,
                temp,
                max_tokens,
            )

        raise RuntimeError(
            "No valid LLM provider configured"
        )

    def _generate_gemini(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Generate text using the Google GenAI SDK."""

        from google.genai import types

        config_kwargs = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }

        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt

        response = self._client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                **config_kwargs
            ),
        )

        return response.text

    def _generate_openai(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Generate text using OpenAI."""

        messages = []

        if system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": system_prompt,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        response = self._client.chat.completions.create(
            model=self._model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content

    def count_tokens(self, text: str) -> int:
        """Approximate token count for the text."""

        try:
            import tiktoken

            enc = tiktoken.encoding_for_model("gpt-4")

            return len(enc.encode(text))

        except Exception:
            return len(text.split()) * 4 // 3


def get_llm(provider: Optional[str] = None) -> LLMClient:
    """Factory function to get an LLM client."""

    return LLMClient(provider=provider)