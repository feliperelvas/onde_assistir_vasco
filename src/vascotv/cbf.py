"""Cliente da API de "onde assistir" da CBF.

A página pública é Next.js e renderiza a tabela vazia (skeleton); os dados vêm
deste proxy JSON do próprio site, sem autenticação — o bundle do site remove o
header Authorization de propósito antes de chamá-lo.
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta  # noqa: F401  (date reexportado para os testes)

import requests

from . import config
from .models import Jogo
from .tls import ca_bundle

log = logging.getLogger(__name__)


class ErroCBF(RuntimeError):
    """A API da CBF não respondeu de forma utilizável."""


def janela_padrao(hoje: date | None = None) -> tuple[date, date]:
    hoje = hoje or date.today()
    return hoje - timedelta(days=config.DIAS_PASSADO), hoje + timedelta(days=config.DIAS_FUTURO)


def _get(sessao: requests.Session, params: dict) -> dict:
    """GET com retry e backoff exponencial. Erro 4xx não é retentado."""
    ultimo: Exception | None = None
    for tentativa in range(config.TENTATIVAS):
        try:
            resposta = sessao.get(config.API_URL, params=params, timeout=config.TIMEOUT)
            if 400 <= resposta.status_code < 500:
                raise ErroCBF(f"HTTP {resposta.status_code} em {resposta.url}")
            resposta.raise_for_status()
            return resposta.json()
        except ErroCBF:
            raise
        except (requests.RequestException, ValueError) as erro:
            ultimo = erro
            if tentativa < config.TENTATIVAS - 1:
                espera = 2**tentativa
                log.warning("Falha na API da CBF (%s); nova tentativa em %ss", erro, espera)
                time.sleep(espera)
    raise ErroCBF(f"API da CBF falhou após {config.TENTATIVAS} tentativas: {ultimo}")


def buscar_jogos(
    campeonato: str,
    data_inicio: date,
    data_fim: date,
    sessao: requests.Session | None = None,
) -> list[Jogo]:
    """Todos os jogos de um campeonato na janela dada, paginando até o fim."""
    propria = sessao is None
    sessao = sessao or requests.Session()
    sessao.headers.update({"Accept": "application/json", "User-Agent": config.USER_AGENT})
    # A CBF não envia o intermediário correto; ver vascotv.tls.
    sessao.verify = ca_bundle()

    try:
        jogos: list[Jogo] = []
        vistos: set[str] = set()
        pagina = 1
        while True:
            corpo = _get(
                sessao,
                {
                    "dataInicio": data_inicio.isoformat(),
                    "dataTermino": data_fim.isoformat(),
                    "campeonato": campeonato,
                    "page": pagina,
                    "pageSize": config.PAGE_SIZE,
                },
            )
            lote = corpo.get("jogos") or []
            for bruto in lote:
                jogo = Jogo.from_api(bruto)
                if jogo.id_jogo and jogo.id_jogo not in vistos:
                    vistos.add(jogo.id_jogo)
                    jogos.append(jogo)

            meta = corpo.get("meta") or {}
            try:
                ultima = int(meta.get("last_page") or 1)
            except (TypeError, ValueError):
                ultima = 1
            # `not lote` protege contra um last_page inflado levar a loop infinito.
            if pagina >= ultima or not lote:
                break
            pagina += 1

        log.info("Campeonato %s: %d jogos na janela", campeonato, len(jogos))
        return jogos
    finally:
        if propria:
            sessao.close()


def buscar_todos(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    campeonatos: dict[str, str] | None = None,
) -> list[Jogo]:
    """Une os campeonatos configurados numa lista só."""
    if data_inicio is None or data_fim is None:
        data_inicio, data_fim = janela_padrao()
    campeonatos = campeonatos or config.CAMPEONATOS

    jogos: list[Jogo] = []
    with requests.Session() as sessao:
        for campeonato in campeonatos:
            jogos.extend(buscar_jogos(campeonato, data_inicio, data_fim, sessao=sessao))
    return jogos
