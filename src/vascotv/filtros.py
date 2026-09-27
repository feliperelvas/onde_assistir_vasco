"""Seleção dos jogos que interessam: Vasco, time profissional masculino.

O ID do time não basta. Série A, Sub-20, SUB17 e Copa do Brasil Feminino usam
todos o mesmo `id=60646`, então a separação profissional/base é pela categoria.
"""

from __future__ import annotations

from enum import Enum

from . import config
from .models import Jogo


class Classificacao(Enum):
    PROFISSIONAL = "profissional"
    BASE = "base"
    DESCONHECIDA = "desconhecida"


def envolve_vasco(jogo: Jogo) -> bool:
    return config.VASCO_ID in (jogo.mandante.id, jogo.visitante.id)


def classificar(jogo: Jogo) -> Classificacao:
    if jogo.categoria_id in config.CATEGORIAS_PROFISSIONAIS:
        return Classificacao.PROFISSIONAL
    if jogo.categoria_id in config.CATEGORIAS_BASE:
        return Classificacao.BASE
    # Categoria nova ou renumerada: incluímos e sinalizamos. Avisar demais é
    # melhor que perder um jogo do profissional em silêncio.
    return Classificacao.DESCONHECIDA


def categoria_incerta(jogo: Jogo) -> bool:
    return classificar(jogo) is Classificacao.DESCONHECIDA


def jogos_do_vasco(jogos: list[Jogo]) -> list[Jogo]:
    """Jogos do profissional do Vasco, ordenados por início."""
    selecionados = [
        jogo
        for jogo in jogos
        if envolve_vasco(jogo) and classificar(jogo) is not Classificacao.BASE
    ]
    return ordenar(selecionados)


def ordenar(jogos: list[Jogo]) -> list[Jogo]:
    def chave(jogo: Jogo):
        inicio = jogo.inicio
        # Jogo com data ilegível vai para o fim, sem estourar a ordenação.
        return (inicio is None, inicio.timestamp() if inicio else 0, jogo.id_jogo)

    return sorted(jogos, key=chave)
