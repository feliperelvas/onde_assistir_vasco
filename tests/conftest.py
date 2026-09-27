import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from vascotv import config  # noqa: E402
from vascotv.models import Jogo  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def payload_api() -> dict:
    """Resposta real da API da CBF (janela de 27/09 a 31/10 de 2026, reduzida)."""
    return json.loads((FIXTURES / "jogos_api.json").read_text(encoding="utf-8"))


@pytest.fixture
def jogos(payload_api) -> list[Jogo]:
    return [Jogo.from_api(bruto) for bruto in payload_api["jogos"]]


@pytest.fixture
def agora() -> datetime:
    """Data fixa anterior a todos os jogos da fixture."""
    return datetime(2026, 9, 28, 10, 0, tzinfo=config.FUSO)


@pytest.fixture
def fazer_jogo():
    """Fábrica de jogos: base realista, campos sobrescritos por palavra-chave."""

    def fabrica(**alteracoes):
        base = {
            "id_jogo": "832172",
            "num_jogo": "281",
            "rodada": "29",
            "grupo": "GRUPO ÚNICO",
            "local": "Nilton Santos - Rio de Janeiro - RJ",
            "data": "07/10/2026",
            "hora": "20:30",
            "mandante": {"id": "20003", "nome": "Botafogo", "url_escudo": ""},
            "visitante": {"id": config.VASCO_ID, "nome": "Vasco da Gama Saf", "url_escudo": ""},
            "transmissoes": [{"nome": "Amazon Prime", "logo": ""}],
            "competicao": {
                "campeonato_id": "42",
                "campeonato_nome": "Campeonato Brasileiro",
                "categoria_id": "1",
                "categoria_nome": "Série A",
            },
        }
        base.update(alteracoes)
        return Jogo.from_api(base)

    return fabrica
