"""Leitura das respostas do FotMob, sem tocar na rede."""

import copy
import json
from datetime import date

import pytest
import requests

from vascotv import config, fotmob
from vascotv.filtros import jogos_do_vasco
from vascotv.render import mensagem_lembrete

from .conftest import FIXTURES


class RespostaFalsa:
    def __init__(self, corpo, status=200):
        self._corpo = corpo
        self.status_code = status
        self.headers = {"Content-Type": "application/json"}

    def raise_for_status(self):
        if self.status_code >= 500:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if isinstance(self._corpo, Exception):
            raise self._corpo
        return self._corpo


class SessaoFalsa:
    """Responde por caminho; para matchDetails, pelo matchId."""

    def __init__(self, respostas: dict):
        self.headers = {}
        self.respostas = respostas
        self.chamadas = []

    def get(self, url, params=None, timeout=None):
        caminho = url.removeprefix(config.FOTMOB_URL)
        self.chamadas.append((caminho, params))
        chave = caminho
        if caminho == "/api/data/matchDetails":
            chave = f"{caminho}?{params['matchId']}"
        return self.respostas[chave]


@pytest.fixture
def gravado() -> dict:
    """Respostas reais de 14/10/2026, reduzidas aos jogos do Vasco."""
    return json.loads((FIXTURES / "fotmob_api.json").read_text(encoding="utf-8"))


def _sessao(gravado, **trocas):
    detalhes = gravado["matchDetails_1000021776"]
    # A ida (1000021775) usa os mesmos detalhes, trocando a perna.
    ida = copy.deepcopy(detalhes)
    ida["content"]["matchFacts"]["infoBox"]["legInfo"]["localizedString"]["key"] = "first_leg"
    respostas = {
        "/api/data/teams": RespostaFalsa(gravado["teams"]),
        "/api/data/tvguide": RespostaFalsa(gravado["tvguide"]),
        "/api/data/matchDetails?1000021776": RespostaFalsa(detalhes),
        "/api/data/matchDetails?1000021775": RespostaFalsa(ida),
    }
    respostas.update(trocas)
    return SessaoFalsa(respostas)


def _buscar(sessao, inicio=date(2026, 10, 1), fim=date(2026, 12, 31)):
    return fotmob.buscar_todos(inicio, fim, sessao=sessao)


def test_so_a_sul_americana_do_vasco(gravado):
    jogos = _buscar(_sessao(gravado))

    assert [j.id_jogo for j in jogos] == ["fotmob-1000021775", "fotmob-1000021776"]


def test_campos_normalizados(gravado):
    volta = _buscar(_sessao(gravado))[1]

    assert volta.data == "20/10/2026"
    assert volta.hora == "21:30"
    assert volta.confronto == "Vasco x Boca Juniors"
    assert volta.em_casa
    assert volta.competicao == "Copa Sul-Americana"
    assert volta.etapa == "Semifinal · volta"
    assert volta.local_formatado == "Estadio Jornalista Mário Filho (Maracanã) — Rio de Janeiro"
    assert volta.onde_assistir == "Paramount+, SBT"


def test_jogo_fora_do_guia_fica_sem_canal(gravado):
    """O guia de 14/10 começa no próprio dia; a ida (13/10, 21:30) já não está nele."""
    ida = _buscar(_sessao(gravado))[0]

    assert ida.etapa == "Semifinal · ida"
    assert ida.transmissoes == ()


def test_passa_pelo_filtro_como_profissional(gravado):
    jogos = _buscar(_sessao(gravado))

    assert jogos_do_vasco(jogos) == jogos


def test_canal_a_confirmar_nao_e_canal(gravado):
    canais = fotmob.canais_do_guia(gravado["tvguide"])

    assert canais["999"] == ()
    assert canais["5103666"] == ("Premiere", "SporTV")


def test_data_e_horario_a_definir(gravado):
    status = gravado["teams"]["fixtures"]["allFixtures"]["fixtures"][2]["status"]
    status["matchTimeTbd"] = True
    volta = _buscar(_sessao(gravado))[1]
    assert (volta.data, volta.hora) == ("20/10/2026", "")
    assert "horário a definir" in mensagem_lembrete([volta])

    status["matchDateTbd"] = True
    volta = _buscar(_sessao(gravado))[1]
    assert (volta.data, volta.hora) == ("", "")
    assert volta.data_hora_curta == "data a definir"


def test_janela_de_datas_poupa_consultas(gravado):
    """Sem jogo da Sul-Americana na janela, nem o guia nem os detalhes são buscados."""
    sessao = _sessao(gravado)
    assert _buscar(sessao, inicio=date(2026, 11, 1), fim=date(2026, 11, 30)) == []
    assert [c for c, _ in sessao.chamadas] == ["/api/data/teams"]


def test_guia_pede_brasil_no_fuso_de_brasilia(gravado):
    sessao = _sessao(gravado)
    _buscar(sessao)

    assert ("/api/data/tvguide", {"country": "br", "timezone": "America/Sao_Paulo"}) in sessao.chamadas


@pytest.mark.parametrize(
    "troca, trecho",
    [
        ({"/api/data/teams": RespostaFalsa({"erro": 1})}, "lista de jogos"),
        ({"/api/data/tvguide": RespostaFalsa({})}, "Guia de TV veio vazio"),
        ({"/api/data/tvguide": RespostaFalsa({"20261020": [{"x": 1}]})}, "guia de TV"),
        ({"/api/data/teams": RespostaFalsa({}, status=403)}, "HTTP 403"),
    ],
)
def test_respostas_quebradas_viram_erro_fotmob(gravado, troca, trecho):
    with pytest.raises(fotmob.ErroFotMob, match=trecho):
        _buscar(_sessao(gravado, **troca))


def test_pagina_de_bloqueio_e_retentada_e_vira_erro(gravado, monkeypatch):
    monkeypatch.setattr(fotmob.time, "sleep", lambda s: None)
    bloqueio = RespostaFalsa(ValueError("Expecting value"), status=202)
    bloqueio.headers = {"Content-Type": "text/html"}
    sessao = _sessao(gravado, **{"/api/data/teams": bloqueio})

    with pytest.raises(fotmob.ErroFotMob, match=r"não é JSON \(HTTP 202, text/html\)"):
        _buscar(sessao)
    assert len(sessao.chamadas) == config.TENTATIVAS
