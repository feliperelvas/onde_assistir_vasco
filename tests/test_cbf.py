"""Cliente HTTP: paginação e retry, sem tocar na rede."""

from datetime import date

import pytest
import requests

from vascotv import cbf, config


class RespostaFalsa:
    def __init__(self, corpo, status=200):
        self._corpo = corpo
        self.status_code = status
        self.url = "https://exemplo/api"

    def raise_for_status(self):
        if self.status_code >= 500:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._corpo


class SessaoFalsa:
    def __init__(self, *respostas):
        self.headers = {}
        self.verify = None
        self.respostas = list(respostas)
        self.chamadas = []

    def get(self, url, params=None, timeout=None):
        self.chamadas.append(params)
        item = self.respostas.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _jogo(id_jogo):
    return {
        "id_jogo": id_jogo,
        "data": "07/10/2026",
        "hora": "20:30",
        "local": "Estádio",
        "rodada": "1",
        "grupo": "",
        "num_jogo": "1",
        "mandante": {"id": "1", "nome": "A"},
        "visitante": {"id": "2", "nome": "B"},
        "transmissoes": [],
        "competicao": {
            "campeonato_id": "42",
            "campeonato_nome": "Campeonato Brasileiro",
            "categoria_id": "1",
            "categoria_nome": "Série A",
        },
    }


def test_percorre_todas_as_paginas():
    sessao = SessaoFalsa(
        RespostaFalsa({"jogos": [_jogo("1")], "meta": {"last_page": 2}}),
        RespostaFalsa({"jogos": [_jogo("2")], "meta": {"last_page": 2}}),
    )

    jogos = cbf.buscar_jogos("42", date(2026, 1, 1), date(2026, 12, 31), sessao=sessao)

    assert [j.id_jogo for j in jogos] == ["1", "2"]
    assert [c["page"] for c in sessao.chamadas] == [1, 2]


def test_remove_duplicados_entre_paginas():
    sessao = SessaoFalsa(
        RespostaFalsa({"jogos": [_jogo("1")], "meta": {"last_page": 2}}),
        RespostaFalsa({"jogos": [_jogo("1")], "meta": {"last_page": 2}}),
    )

    jogos = cbf.buscar_jogos("42", date(2026, 1, 1), date(2026, 12, 31), sessao=sessao)

    assert [j.id_jogo for j in jogos] == ["1"]


def test_pagina_vazia_interrompe_last_page_inflado():
    """Sem isso, um last_page errado viraria loop até estourar as respostas."""
    sessao = SessaoFalsa(
        RespostaFalsa({"jogos": [_jogo("1")], "meta": {"last_page": 99}}),
        RespostaFalsa({"jogos": [], "meta": {"last_page": 99}}),
    )

    jogos = cbf.buscar_jogos("42", date(2026, 1, 1), date(2026, 12, 31), sessao=sessao)

    assert len(jogos) == 1
    assert len(sessao.chamadas) == 2


def test_erro_4xx_nao_e_retentado():
    sessao = SessaoFalsa(RespostaFalsa({}, status=404))

    with pytest.raises(cbf.ErroCBF, match="404"):
        cbf.buscar_jogos("42", date(2026, 1, 1), date(2026, 12, 31), sessao=sessao)

    assert len(sessao.chamadas) == 1


def test_falha_de_rede_e_retentada(monkeypatch):
    monkeypatch.setattr(cbf.time, "sleep", lambda _: None)
    sessao = SessaoFalsa(
        requests.ConnectionError("caiu"),
        RespostaFalsa({"jogos": [_jogo("1")], "meta": {"last_page": 1}}),
    )

    jogos = cbf.buscar_jogos("42", date(2026, 1, 1), date(2026, 12, 31), sessao=sessao)

    assert len(jogos) == 1
    assert len(sessao.chamadas) == 2


def test_desiste_depois_do_limite_de_tentativas(monkeypatch):
    monkeypatch.setattr(cbf.time, "sleep", lambda _: None)
    sessao = SessaoFalsa(*[requests.ConnectionError("caiu")] * config.TENTATIVAS)

    with pytest.raises(cbf.ErroCBF, match="tentativas"):
        cbf.buscar_jogos("42", date(2026, 1, 1), date(2026, 12, 31), sessao=sessao)

    assert len(sessao.chamadas) == config.TENTATIVAS


def test_janela_padrao_cobre_passado_curto_e_temporada_seguinte():
    inicio, fim = cbf.janela_padrao(date(2026, 9, 27))

    assert inicio == date(2026, 9, 20)
    assert (fim - inicio).days == config.DIAS_PASSADO + config.DIAS_FUTURO
