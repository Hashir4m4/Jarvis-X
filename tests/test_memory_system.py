import pytest
from backend.memory.memory_models import MemoryDecision, MemoryCategory, MemoryImportance, PrivacyLevel, MemoryConfidence
from backend.memory.memory_api import MemoryAPI
from unittest.mock import MagicMock

class MockVault:
    def _slugify(self, text): return text.replace(" ", "_")
    def write_note(self, category, filename, content, metadata=None): return f"/vault/{filename}"
    def search_notes(self, query, limit=5): return []

class MockSQLite:
    def add_message(self, session_id, role, content): return 1

class MockChroma:
    def __init__(self): self.memories = []
    def add_memory(self, doc_id, text, metadata): self.memories.append({"id": doc_id, "text": text, "metadata": metadata})
    def search_memory(self, query, n_results=5): return self.memories[:n_results]
    def query_similar(self, query, n_results=5): return self.memories[:n_results]

@pytest.fixture
def mock_memory_api():
    api = MemoryAPI({"memory_advanced": {}}, session_id="test")
    api.vault = MockVault()
    api.sqlite = MockSQLite()
    api.chroma = MockChroma()
    return api

def test_temporary_conversation_not_saved(mock_memory_api):
    res = mock_memory_api.write_memory("What's 5+5?", category="temporary")
    assert res.get("status") == "ignored_temporary"
    assert len(mock_memory_api.chroma.memories) == 0

def test_explicit_remember(mock_memory_api):
    res = mock_memory_api.write_memory("Remember that JARVIS is cool", category="long_term", metadata={"importance": "high"})
    assert res.get("status") == "stored"
    assert len(mock_memory_api.chroma.memories) == 1
    assert mock_memory_api.chroma.memories[0]["metadata"]["importance"] == "high"

def test_memory_models_extended():
    decision = MemoryDecision(
        should_save=True,
        category=MemoryCategory.PROJECT,
        importance=MemoryImportance.CRITICAL,
        privacy_level=PrivacyLevel.LOCAL_ONLY,
        confidence=MemoryConfidence.USER_STATED
    )
    assert decision.privacy_level == "local_only"
