from qdrant_client import QdrantClient

from andes_agent.rag import HashEmbedder, RepositorioPoliticas


def _repo() -> RepositorioPoliticas:
    repo = RepositorioPoliticas(QdrantClient(":memory:"), HashEmbedder(), "test_politicas")
    assert repo.indexar() >= 8
    return repo


def test_rag_cita_fuente_y_seccion():
    r = _repo().buscar("cliente en hold crédito bloqueado", k=3)
    assert ("politica_credito.md", "Cliente en hold") in {(x["fuente"], x["seccion"]) for x in r}


def test_rag_plazos_de_entrega():
    r = _repo().buscar("plazo de entrega lead time", k=3)
    assert "politica_entrega.md" in {x["fuente"] for x in r}


def test_rag_umbral_descarta_consultas_sin_relacion():
    assert _repo().buscar("receta de ceviche con camote", k=3, umbral=0.5) == []
