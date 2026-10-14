"""Leitura do JSON da CONMEBOL, sem tocar na rede."""

import json
from datetime import date

import pytest

from vascotv import conmebol
from vascotv.filtros import jogos_do_vasco
from vascotv.render import mensagem_lembrete

from .conftest import FIXTURES


class RespostaFalsa:
    def __init__(self, corpo, status=200):
        self._corpo = corpo
        self.status_code = status
        self.url = "https://exemplo/api"
        self.headers = {}
        self.text = ""

    def raise_for_status(self):
        pass

    def json(self):
        return self._corpo


class SessaoFalsa:
    def __init__(self, resposta):
        self.resposta = resposta
        self.urls = []

    def get(self, url, timeout=None):
        self.urls.append(url)
        return self.resposta


@pytest.fixture
def payload() -> dict:
    """Resposta real do torneio 104 (Sul-Americana 2026) em 14/10, reduzida."""
    return json.loads((FIXTURES / "conmebol_api.json").read_text(encoding="utf-8"))


def _buscar(payload, inicio=date(2026, 1, 1), fim=date(2026, 12, 31)):
    sessao = SessaoFalsa(RespostaFalsa(payload))
    jogos = conmebol.buscar_jogos(
        "sudamericana", "104", "Copa Sul-Americana", inicio, fim, sessao
    )
    return jogos, sessao


def test_so_jogos_do_vasco(payload):
    jogos, sessao = _buscar(payload)

    assert [j.id_jogo for j in jogos] == ["conmebol-1712", "conmebol-1725", "conmebol-1719"]
    assert sessao.urls == [
        "https://gol.conmebol.com/sudamericana/pt-br/api/v2/tournament-fixtures/104"
    ]


def test_campos_normalizados(payload):
    jogos, _ = _buscar(payload)
    volta = next(j for j in jogos if j.id_jogo == "conmebol-1719")

    assert volta.data == "20/10/2026"
    assert volta.hora == "21:30"
    assert volta.confronto == "Vasco x Boca Juniors"
    assert volta.em_casa
    assert volta.competicao == "Copa Sul-Americana"
    assert volta.etapa == "Semifinal"
    assert volta.local_formatado == "Estadio Jornalista Mário Filho (Maracanã)"
    assert volta.onde_assistir == "Paramount+, SBT"


def test_vasco_passa_pelo_filtro_como_profissional(payload):
    """O ID do Vasco é traduzido para o da CBF e a categoria conta como profissional."""
    jogos, _ = _buscar(payload)

    assert jogos_do_vasco(jogos) == jogos


def test_emissora_de_outro_pais_e_ignorada(payload):
    """A lista varia pelo país de quem acessa; canal estrangeiro seria informação errada."""
    payload["match"][2]["matchInfo"]["broadcasts"] = [
        {"id": 1, "name": "Sudamericana_ESPN_USA", "link": ""}
    ]
    jogos, _ = _buscar(payload)
    volta = next(j for j in jogos if j.id_jogo == "conmebol-1719")

    assert volta.transmissoes == ()
    assert volta.onde_assistir == "Não informado"


def test_emissora_desconhecida_aparece_com_nome_derivado():
    assert conmebol.nome_emissora("Sudamericana_Globo_Play_Brazil") == "Globo Play"
    assert conmebol.nome_emissora("Sudamericana_SBT_Brazil") == "SBT"


def test_horario_a_confirmar_fica_sem_hora(payload):
    vasco_na_final = payload["match"][4]
    vasco_na_final["matchInfo"]["contestant"] = [
        {"id": 97, "name": "Vasco da Gama", "position": "home"},
        {"id": 53, "name": "Boca Juniors", "position": "away"},
    ]
    jogos, _ = _buscar(payload)
    final = next(j for j in jogos if j.id_jogo == "conmebol-1727")

    assert final.data == "21/11/2026"
    assert final.hora == ""
    assert final.etapa == "Final"
    assert "horário a definir" in mensagem_lembrete([final])


def test_janela_de_datas(payload):
    jogos, _ = _buscar(payload, inicio=date(2026, 10, 14), fim=date(2026, 10, 31))

    assert [j.id_jogo for j in jogos] == ["conmebol-1719"]


def test_resposta_sem_lista_de_jogos_e_erro():
    with pytest.raises(conmebol.ErroCONMEBOL):
        _buscar({"erro": "manutenção"})


def test_http_4xx_nao_e_retentado(monkeypatch):
    sessao = SessaoFalsa(RespostaFalsa({}, status=404))
    with pytest.raises(conmebol.ErroCONMEBOL, match="HTTP 404"):
        conmebol.buscar_jogos(
            "sudamericana", "999", "X", date(2026, 1, 1), date(2026, 12, 31), sessao
        )
    assert len(sessao.urls) == 1
