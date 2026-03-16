import pytest
from app.rag.embeddings import get_embedding, get_embeddings, build_endpoint_text, _mock_embedding, EMBEDDING_DIM


class TestMockEmbeddings:
    def test_embedding_dimension(self):
        emb = _mock_embedding("test text")
        assert len(emb) == EMBEDDING_DIM

    def test_deterministic(self):
        emb1 = _mock_embedding("hello world")
        emb2 = _mock_embedding("hello world")
        assert emb1 == emb2

    def test_different_texts_different_vectors(self):
        emb1 = _mock_embedding("hello")
        emb2 = _mock_embedding("goodbye")
        assert emb1 != emb2

    def test_normalized(self):
        import math
        emb = _mock_embedding("test")
        norm = math.sqrt(sum(x * x for x in emb))
        assert abs(norm - 1.0) < 1e-6

    def test_get_embedding_mock_mode(self, mock_settings):
        from unittest.mock import patch
        with patch("app.rag.embeddings.get_settings", return_value=mock_settings):
            result = get_embedding("test text")
        assert len(result) == EMBEDDING_DIM

    def test_get_embedding_empty_raises(self):
        with pytest.raises(ValueError):
            get_embedding("")

    def test_get_embedding_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            get_embedding("   ")

    def test_get_embeddings_batch(self, mock_settings):
        from unittest.mock import patch
        with patch("app.rag.embeddings.get_settings", return_value=mock_settings):
            results = get_embeddings(["text1", "text2", "text3"])
        assert len(results) == 3
        assert all(len(r) == EMBEDDING_DIM for r in results)

    def test_get_embeddings_empty_list_raises(self):
        with pytest.raises(ValueError):
            get_embeddings([])

    def test_get_embeddings_empty_text_in_list_raises(self):
        with pytest.raises(ValueError, match="index 1"):
            get_embeddings(["valid", "", "also valid"])


class TestBuildEndpointText:
    def test_basic_endpoint(self):
        ep = {"method": "GET", "path": "/users", "summary": "List users"}
        text = build_endpoint_text(ep)
        assert "GET /users" in text
        assert "List users" in text

    def test_endpoint_with_params(self):
        ep = {"method": "POST", "path": "/orders", "parameters": [{"name": "limit"}, {"name": "offset"}]}
        text = build_endpoint_text(ep)
        assert "limit" in text
        assert "offset" in text

    def test_empty_endpoint(self):
        text = build_endpoint_text({})
        assert text == ""

    def test_endpoint_with_tags(self):
        ep = {"method": "GET", "path": "/test", "tags": ["auth", "users"]}
        text = build_endpoint_text(ep)
        assert "auth" in text

    def test_endpoint_with_description(self):
        ep = {"method": "GET", "path": "/test", "description": "A detailed description"}
        text = build_endpoint_text(ep)
        assert "A detailed description" in text

    def test_parts_joined_with_pipe(self):
        ep = {"method": "GET", "path": "/test", "summary": "Summary"}
        text = build_endpoint_text(ep)
        assert " | " in text
