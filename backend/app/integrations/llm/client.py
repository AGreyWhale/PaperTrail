from collections.abc import Iterator

import openai
from openai import OpenAI


class LLMUnavailableError(Exception):
    """When the LLM provider errors, times out, or rejects the request"""


class LLMClient:
    """Wraps an OpenAI-compatible chat completions endpoint.
    Nothing here is provider-specific, so a swap is a Settings change.
    Accepts an optional pre-built client for tests"""

    def __init__(self, *, api_key: str, base_url: str, model: str, client: OpenAI | None = None):
        self._model = model
        self._client = client or OpenAI(api_key=api_key, base_url=base_url)

    def complete(self, *, system: str, user: str, json_mode: bool = False) -> str:
        #json_mode asks the provider to guarantee syntactically valid JSON.
        #It guarantees shape, not correctness, so callers still validate
        extra = {"response_format": {"type": "json_object"}} if json_mode else {}
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                # Grounded Q&A over retrieved text wants low creativity.
                temperature=0.2,
                **extra,
            )
        except openai.APIError as exc:
            raise LLMUnavailableError(_provider_message(exc)) from exc

        return response.choices[0].message.content or ""

    def stream_complete(self, *, system: str, user: str) -> Iterator[str]:
        #Same call with stream=True, yielding text deltas as they arrive.
        #Provider errors can surface mid-iteration, so the whole loop is
        #wrapped rather than just the initial request
        try:
            stream = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.2,
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except openai.APIError as exc:
            raise LLMUnavailableError(_provider_message(exc)) from exc


def _provider_message(exc: openai.APIError) -> str:
    #Digs the provider's own wording out, so a bad model name or a
    #revoked key reaches the user instead of a bare 500
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        # The SDK usually unwraps the {"error": {...}} envelope for us,
        # but not every OpenAI-compatible provider gets that far.
        nested = body.get("error")
        message = body.get("message") or (isinstance(nested, dict) and nested.get("message"))
        if message:
            return message
    return str(exc)
