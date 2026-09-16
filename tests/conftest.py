"""
tests/conftest.py — shared test bootstrap.

The LexRisk analysis stack depends on heavy third-party packages (torch,
sentence-transformers, the Groq/OpenAI SDKs, psycopg2, streamlit). Unit tests
must not require them, so any that are genuinely absent are replaced with
minimal stubs BEFORE the test modules import application code.

If a real package is installed it is always preferred — nothing is shadowed.
"""

import importlib.util
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _installed(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _stub(name: str, **attrs) -> types.ModuleType:
    mod = sys.modules.get(name) or types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    sys.modules[name] = mod
    return mod


class _StubLLMClient:
    """Stands in for a Groq/OpenAI client: constructible, never called in unit tests."""

    def __init__(self, *args, **kwargs):
        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=self._unavailable)
        )

    @staticmethod
    def _unavailable(*args, **kwargs):
        raise RuntimeError("Stub LLM client: no network calls in unit tests")


class _StubSentenceTransformer:
    def __init__(self, *args, **kwargs):
        pass

    def encode(self, texts, **kwargs):
        return [[0.0] for _ in texts]


def _install_stubs() -> None:
    if not _installed("dotenv"):
        _stub("dotenv", load_dotenv=lambda *a, **k: None)

    if not _installed("groq"):
        _stub("groq", Groq=_StubLLMClient)

    if not _installed("openai"):
        _stub("openai", OpenAI=_StubLLMClient)

    if not _installed("sentence_transformers"):
        _stub("sentence_transformers", SentenceTransformer=_StubSentenceTransformer)

    if not _installed("sklearn"):
        sklearn = _stub("sklearn")
        metrics = _stub("sklearn.metrics")
        pairwise = _stub("sklearn.metrics.pairwise", cosine_similarity=lambda a, b: [])
        sklearn.metrics = metrics
        metrics.pairwise = pairwise

    if not _installed("numpy"):
        _stub("numpy", argmax=lambda row: max(range(len(row)), key=lambda i: row[i]))

    if not _installed("psycopg2"):
        pg = _stub("psycopg2", connect=lambda *a, **k: None)
        pg.pool = _stub("psycopg2.pool", ThreadedConnectionPool=object)
        pg.extras = _stub("psycopg2.extras", RealDictCursor=object)


_install_stubs()
