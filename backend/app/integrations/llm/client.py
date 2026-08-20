from openai import OpenAI


class LLMClient:
    """Wraps an OpenAI-compatible chat completions endpoint.
    Nothing here is provider-specific, so a swap is a Settings change.
    Accepts an optional pre-built client for tests"""

    def __init__(self, *, api_key: str, base_url: str, model: str, client: OpenAI | None = None):
        self._model = model
        self._client = client or OpenAI(api_key=api_key, base_url=base_url)

    def complete(self, *, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            # Grounded Q&A over retrieved text wants low creativity.
            temperature=0.2,
        )
        return response.choices[0].message.content or ""
