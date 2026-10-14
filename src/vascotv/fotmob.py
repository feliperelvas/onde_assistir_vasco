"""Cliente do FotMob, usado para a Copa Sul-Americana.

Três consultas, todas JSON e sem autenticação:

- `/api/data/teams?id=10276` — a temporada inteira do Vasco, com datas;
- `/api/data/tvguide?country=br` — canais no Brasil dos jogos dos próximos 7
  dias. O país vai na URL, então a resposta não depende de onde o runner está;
- `/api/data/matchDetails?matchId=…` — estádio, fase e ida/volta, só para os
  poucos jogos da Sul-Americana na janela.

Jogo a mais de 7 dias vem sem canal ("Não informado"); quando entra no guia, o
diff avisa a mudança de transmissão. Qualquer resposta fora do formato esperado
vira ErroFotMob, que o `sync` transforma em aviso no Telegram.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime

import requests

from . import config
from .models import Jogo, Time

log = logging.getLogger(__name__)

PERNAS = {"first_leg": "ida", "second_leg": "volta"}


class ErroFotMob(RuntimeError):
    """O FotMob não respondeu de forma utilizável."""


def _get(sessao: requests.Session, caminho: str, params: dict) -> dict:
    """GET com retry e backoff exponencial. Erro 4xx não é retentado."""
    url = f"{config.FOTMOB_URL}{caminho}"
    ultimo: Exception | None = None
    for tentativa in range(config.TENTATIVAS):
        try:
            resposta = sessao.get(url, params=params, timeout=config.TIMEOUT)
            if 400 <= resposta.status_code < 500:
                raise ErroFotMob(f"HTTP {resposta.status_code} em {caminho}")
            resposta.raise_for_status()
            try:
                corpo = resposta.json()
            except ValueError as erro:
                # Página de bloqueio ou desafio anti-robô costuma vir assim.
                raise ValueError(
                    f"resposta não é JSON (HTTP {resposta.status_code}, "
                    f"{resposta.headers.get('Content-Type')})"
                ) from erro
            if not isinstance(corpo, dict):
                raise ErroFotMob(f"Resposta inesperada em {caminho}: {type(corpo).__name__}")
            return corpo
        except ErroFotMob:
            raise
        except (requests.RequestException, ValueError) as erro:
            ultimo = erro
            if tentativa < config.TENTATIVAS - 1:
                espera = 2**tentativa
                log.warning("Falha no FotMob (%s); nova tentativa em %ss", erro, espera)
                time.sleep(espera)
    raise ErroFotMob(f"{caminho} falhou após {config.TENTATIVAS} tentativas: {ultimo}")


def _inicio(bruto: dict) -> datetime:
    utc = datetime.fromisoformat(bruto["status"]["utcTime"].replace("Z", "+00:00"))
    return utc.astimezone(config.FUSO)


def _time(bruto: dict) -> Time:
    id_fotmob = str(bruto["id"])
    # O Vasco ganha o ID da CBF para que filtros e "em casa" funcionem igual; os
    # outros levam prefixo para nunca colidir com um ID da CBF.
    if id_fotmob == config.FOTMOB_VASCO_ID:
        return Time(id=config.VASCO_ID, nome=bruto["name"])
    return Time(id=f"fotmob:{id_fotmob}", nome=bruto["name"])


def canais_do_guia(guia: dict) -> dict[str, tuple[str, ...]]:
    """ID do jogo -> canais no Brasil, a partir da resposta do tvguide."""
    canais: dict[str, tuple[str, ...]] = {}
    for ligas in guia.values():
        for liga in ligas:
            for jogo in liga["matches"]:
                nomes = {
                    (canal.get("name") or "").strip()
                    for canal in jogo.get("channels") or []
                }
                nomes -= config.FOTMOB_SEM_CANAL | {""}
                canais[str(jogo["id"])] = tuple(sorted(nomes))
    return canais


def _etapa(detalhes: dict) -> str:
    info = (detalhes.get("content") or {}).get("matchFacts", {}).get("infoBox") or {}
    rodada = (info.get("Tournament") or {}).get("round") or ""
    rodada = config.FOTMOB_FASES.get(rodada, rodada)
    perna = PERNAS.get(((info.get("legInfo") or {}).get("localizedString") or {}).get("key"))
    return f"{rodada} · {perna}" if rodada and perna else rodada


def _local(detalhes: dict) -> str:
    info = (detalhes.get("content") or {}).get("matchFacts", {}).get("infoBox") or {}
    estadio = info.get("Stadium") or {}
    nome = (estadio.get("name") or "").strip()
    # "Rio de Janeiro, Rio de Janeiro" -> "Rio de Janeiro".
    cidade = (estadio.get("city") or "").split(",")[0].strip()
    # O " - " é o separador que models.formatar_local entende.
    return f"{nome} - {cidade}" if nome and cidade else nome


def jogo_from_api(bruto: dict, detalhes: dict, canais: tuple[str, ...]) -> Jogo:
    status = bruto["status"]
    inicio = _inicio(bruto)
    liga = str(bruto["tournament"]["leagueId"])
    data = "" if status.get("matchDateTbd") else f"{inicio:%d/%m/%Y}"
    hora = "" if data == "" or status.get("matchTimeTbd") else f"{inicio:%H:%M}"
    return Jogo(
        id_jogo=f"fotmob-{bruto['id']}",
        data=data,
        hora=hora,
        local=_local(detalhes),
        rodada=_etapa(detalhes),
        grupo="",
        num_jogo="",
        mandante=_time(bruto["home"]),
        visitante=_time(bruto["away"]),
        transmissoes=canais,
        campeonato_id=f"fotmob-{liga}",
        campeonato_nome=config.FOTMOB_LIGAS[liga],
        categoria_id=config.CATEGORIA_FOTMOB,
        categoria_nome="",
    )


def buscar_todos(
    data_inicio: date, data_fim: date, sessao: requests.Session | None = None
) -> list[Jogo]:
    """Jogos do Vasco nas ligas de FOTMOB_LIGAS dentro da janela."""
    propria = sessao is None
    sessao = sessao or requests.Session()
    sessao.headers.update({"Accept": "application/json", "User-Agent": config.USER_AGENT})
    try:
        time_ = _get(sessao, "/api/data/teams", {"id": config.FOTMOB_VASCO_ID})
        try:
            selecionados = [
                bruto
                for bruto in time_["fixtures"]["allFixtures"]["fixtures"]
                if str(bruto["tournament"]["leagueId"]) in config.FOTMOB_LIGAS
                and data_inicio <= _inicio(bruto).date() <= data_fim
            ]
        except (KeyError, TypeError, ValueError) as erro:
            raise ErroFotMob(f"Formato inesperado da lista de jogos: {erro!r}") from erro

        if not selecionados:
            log.info("FotMob: nenhum jogo do Vasco nas ligas acompanhadas")
            return []

        guia = _get(
            sessao,
            "/api/data/tvguide",
            {"country": config.FOTMOB_PAIS, "timezone": config.FUSO.key},
        )
        try:
            canais = canais_do_guia(guia)
        except (KeyError, TypeError, AttributeError) as erro:
            raise ErroFotMob(f"Formato inesperado do guia de TV: {erro!r}") from erro
        # Guia vazio não é "nenhum jogo passa na TV": o guia sempre tem dezenas.
        if not canais:
            raise ErroFotMob("Guia de TV veio vazio")

        jogos: list[Jogo] = []
        for bruto in selecionados:
            detalhes = _get(sessao, "/api/data/matchDetails", {"matchId": bruto["id"]})
            try:
                jogos.append(jogo_from_api(bruto, detalhes, canais.get(str(bruto["id"]), ())))
            except (KeyError, TypeError, ValueError) as erro:
                raise ErroFotMob(f"Formato inesperado do jogo {bruto.get('id')}: {erro!r}") from erro

        log.info("FotMob: %d jogo(s) do Vasco na janela", len(jogos))
        return jogos
    finally:
        if propria:
            sessao.close()
