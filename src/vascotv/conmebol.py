"""Cliente do site oficial da CONMEBOL (gol.conmebol.com), para a Sul-Americana.

A página de jogos do torneio é Drupal e monta a lista no navegador a partir de
um JSON do próprio site, sem autenticação. Ele traz a temporada inteira de uma
vez (~160 jogos, ~2 MB) e, por jogo, as emissoras que a CONMEBOL divulga.

As emissoras dependem do país de quem pergunta: a resposta varia pelo header
`CloudFront-Viewer-Country`, e os nomes vêm com o país no fim
(`Sudamericana_Paramount_Brazil`). Por isso só aceitamos as que terminam em
`_Brazil` — se o runner, que fica fora do Brasil, receber as de outro país, o
jogo aparece como "Não informado" em vez de com o canal errado.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime

import requests

from . import config
from .models import Jogo, Time

log = logging.getLogger(__name__)

SUFIXO_BRASIL = "_Brazil"


class ErroCONMEBOL(RuntimeError):
    """O site da CONMEBOL não respondeu de forma utilizável."""


def _get(sessao: requests.Session, url: str) -> dict:
    """GET com retry e backoff exponencial. Erro 4xx não é retentado."""
    ultimo: Exception | None = None
    for tentativa in range(config.TENTATIVAS):
        try:
            resposta = sessao.get(url, timeout=config.TIMEOUT)
            if 400 <= resposta.status_code < 500:
                raise ErroCONMEBOL(f"HTTP {resposta.status_code} em {resposta.url}")
            resposta.raise_for_status()
            return resposta.json()
        except ErroCONMEBOL:
            raise
        except (requests.RequestException, ValueError) as erro:
            ultimo = erro
            if tentativa < config.TENTATIVAS - 1:
                espera = 2**tentativa
                log.warning("Falha no site da CONMEBOL (%s); nova tentativa em %ss", erro, espera)
                time.sleep(espera)
    raise ErroCONMEBOL(f"Site da CONMEBOL falhou após {config.TENTATIVAS} tentativas: {ultimo}")


def nome_emissora(bruto: str) -> str:
    """'Sudamericana_ESPN_Disney_Brazil' -> 'ESPN / Disney+'."""
    if bruto in config.CONMEBOL_EMISSORAS:
        return config.CONMEBOL_EMISSORAS[bruto]
    # Emissora nova: melhor um nome feio que sumir com ela.
    miolo = bruto.removesuffix(SUFIXO_BRASIL)
    for torneio in config.CONMEBOL_TORNEIOS.values():
        miolo = miolo.removeprefix(f"{torneio['prefixo_emissora']}_")
    return miolo.replace("_", " ").strip()


def _time(bruto: dict) -> Time:
    id_conmebol = str(bruto.get("id") or "")
    # O Vasco ganha o ID da CBF para que filtros e "em casa" funcionem igual; os
    # outros levam prefixo para nunca colidir com um ID da CBF.
    if id_conmebol == config.CONMEBOL_VASCO_ID:
        id_time = config.VASCO_ID
    else:
        id_time = f"conmebol:{id_conmebol}"
    return Time(id=id_time, nome=(bruto.get("name") or "").strip())


def _fase(bruto: dict) -> str:
    nome = ((bruto.get("stage") or {}).get("name") or "").strip()
    return config.CONMEBOL_FASES.get(nome, nome)


def jogo_from_api(bruto: dict, torneio_id: str, torneio_nome: str) -> Jogo | None:
    """Converte um jogo do JSON da CONMEBOL; None se faltar o essencial."""
    info = bruto.get("matchInfo") or {}
    contestantes = info.get("contestant") or []
    mandante = next((c for c in contestantes if c.get("position") == "home"), None)
    visitante = next((c for c in contestantes if c.get("position") == "away"), None)
    if not info.get("id") or mandante is None or visitante is None:
        return None

    data = hora = ""
    if isinstance(info.get("date"), (int, float)):
        inicio = datetime.fromtimestamp(info["date"], config.FUSO)
        data = f"{inicio:%d/%m/%Y}"
        # `tbc` = horário a confirmar; a data vem com uma hora qualquer.
        hora = "" if info.get("tbc") else f"{inicio:%H:%M}"

    transmissoes = tuple(
        sorted(
            {
                nome_emissora(b["name"])
                for b in (info.get("broadcasts") or [])
                if (b.get("name") or "").endswith(SUFIXO_BRASIL)
            }
        )
    )

    return Jogo(
        id_jogo=f"conmebol-{info['id']}",
        data=data,
        hora=hora,
        local=((info.get("venue") or {}).get("longName") or "").strip(),
        rodada=_fase(info),
        grupo="",
        num_jogo="",
        mandante=_time(mandante),
        visitante=_time(visitante),
        transmissoes=transmissoes,
        campeonato_id=f"conmebol-{torneio_id}",
        campeonato_nome=torneio_nome,
        categoria_id=config.CATEGORIA_CONMEBOL,
        categoria_nome="",
    )


def buscar_jogos(
    caminho: str,
    torneio_id: str,
    torneio_nome: str,
    data_inicio: date,
    data_fim: date,
    sessao: requests.Session,
) -> list[Jogo]:
    """Jogos do Vasco num torneio da CONMEBOL, dentro da janela dada."""
    url = f"{config.CONMEBOL_URL}/{caminho}/pt-br/api/v2/tournament-fixtures/{torneio_id}"
    corpo = _get(sessao, url)
    if not isinstance(corpo.get("match"), list):
        raise ErroCONMEBOL(f"Resposta sem a lista 'match' em {url}")

    jogos: list[Jogo] = []
    for bruto in corpo["match"]:
        contestantes = (bruto.get("matchInfo") or {}).get("contestant") or []
        # Só o Vasco: o torneio inteiro vem na resposta.
        if not any(str(c.get("id")) == config.CONMEBOL_VASCO_ID for c in contestantes):
            continue
        jogo = jogo_from_api(bruto, torneio_id, torneio_nome)
        if jogo is None:
            continue
        inicio = jogo.inicio
        dia = inicio.date() if inicio else _dia(jogo.data)
        if dia is None or data_inicio <= dia <= data_fim:
            jogos.append(jogo)

    log.info("%s: %d jogo(s) do Vasco na janela", torneio_nome, len(jogos))
    return jogos


def _dia(texto: str) -> date | None:
    try:
        return datetime.strptime(texto, "%d/%m/%Y").date()
    except ValueError:
        return None


def buscar_todos(data_inicio: date, data_fim: date) -> list[Jogo]:
    """Une os torneios da CONMEBOL configurados numa lista só."""
    jogos: list[Jogo] = []
    with requests.Session() as sessao:
        sessao.headers.update({"Accept": "application/json", "User-Agent": config.USER_AGENT})
        for torneio_id, torneio in config.CONMEBOL_TORNEIOS.items():
            jogos.extend(
                buscar_jogos(
                    torneio["caminho"], torneio_id, torneio["nome"], data_inicio, data_fim, sessao
                )
            )
    return jogos
