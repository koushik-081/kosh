from functools import lru_cache
from collections.abc import Iterator
from openai import OpenAI

from app.config import get_settings


@lru_cache
def _llm_client() -> OpenAI:
    s = get_settings()
    return OpenAI(base_url=s.llm_base_url, api_key=s.llm_api_key)


@lru_cache
def _embed_client() -> OpenAI:
    s = get_settings()
    return OpenAI(base_url=s.embed_base_url, api_key=s.llm_api_key)


def chat(messages: list[dict], fast: bool = False, temperature: float = 0.0) -> str:
    """Send a conversation to the LLM and return its reply.

    fast=True uses the small model (grading, rewriting); otherwise the answer model.
    """
    s = get_settings()
    model = s.fast_model if fast else s.gen_model
    resp = _llm_client().chat.completions.create(
        model=model, messages=messages, temperature=temperature
    )
    return resp.choices[0].message.content or ""


def embed(texts: list[str]) -> list[list[float]]:
    """Turn each text into a vector of EMBED_DIM numbers."""
    s = get_settings()
    resp = _embed_client().embeddings.create(model=s.embed_model, input=texts)
    vectors = [d.embedding for d in resp.data]
    if vectors and len(vectors[0]) != s.embed_dim:
        raise ValueError(
            f"{s.embed_model} returned {len(vectors[0])} dims, EMBED_DIM is {s.embed_dim}"
        )
    return vectors


def chat_stream(messages: list[dict], fast: bool = False, temperature: float = 0.0) -> Iterator[str]:
    """Like chat(), but yields the reply piece by piece as the model writes it."""
    s = get_settings()
    model = s.fast_model if fast else s.gen_model
    stream = _llm_client().chat.completions.create(
        model=model, messages=messages, temperature=temperature, stream=True
    )
    for event in stream:
        if event.choices and event.choices[0].delta.content:
            yield event.choices[0].delta.content
