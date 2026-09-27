"""Comparação entre o snapshot anterior e o recém-buscado.

É o núcleo do projeto: o site da CBF já mostra a tabela, o que ele não faz é
avisar quando algo muda. Datas, horários e transmissões mudam com frequência, e
rodadas novas aparecem aos poucos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from . import config
from .models import Jogo, exibir_time

# Campos observados, na ordem em que aparecem na mensagem. O placar (`gols`) fica
# fora de propósito — nem é modelado — porque mudaria a cada gol durante o jogo.
LABELS = {
    "data": "data",
    "hora": "horário",
    "local": "local",
    "transmissoes": "transmissão",
    "rodada": "rodada",
    "mandante": "mandante",
    "visitante": "visitante",
    "categoria": "categoria",
}


def _valores(jogo: Jogo) -> dict[str, str]:
    return {
        "data": jogo.data,
        "hora": jogo.hora,
        "local": jogo.local_formatado,
        "transmissoes": jogo.onde_assistir,
        "rodada": jogo.rodada,
        "mandante": exibir_time(jogo.mandante.nome),
        "visitante": exibir_time(jogo.visitante.nome),
        "categoria": jogo.categoria_nome,
    }


@dataclass(frozen=True)
class Mudanca:
    campo: str
    de: str
    para: str

    @property
    def label(self) -> str:
        return LABELS.get(self.campo, self.campo)


@dataclass(frozen=True)
class JogoNovo:
    jogo: Jogo


@dataclass(frozen=True)
class JogoRemovido:
    jogo: Jogo


@dataclass(frozen=True)
class JogoAlterado:
    antes: Jogo
    depois: Jogo
    mudancas: tuple[Mudanca, ...]

    @property
    def jogo(self) -> Jogo:
        return self.depois


Evento = JogoNovo | JogoRemovido | JogoAlterado


def _futuro(jogo: Jogo, agora: datetime) -> bool:
    """Só jogos que ainda vão acontecer geram aviso.

    Sem isso, todo jogo que envelhece e sai da janela de consulta (hoje − 7 dias)
    seria anunciado como "removido do calendário", e correções em jogos já
    disputados virariam ruído.  Data ilegível conta como futuro: melhor avisar.
    """
    inicio = jogo.inicio
    return inicio is None or inicio >= agora


def comparar(antes: list[Jogo], depois: list[Jogo], agora: datetime | None = None) -> list[Evento]:
    agora = agora or datetime.now(config.FUSO)
    mapa_antes = {jogo.chave: jogo for jogo in antes}
    mapa_depois = {jogo.chave: jogo for jogo in depois}

    eventos: list[Evento] = []

    for chave, jogo in mapa_depois.items():
        anterior = mapa_antes.get(chave)
        if anterior is None:
            if _futuro(jogo, agora):
                eventos.append(JogoNovo(jogo))
            continue

        velhos, novos = _valores(anterior), _valores(jogo)
        mudancas = tuple(
            Mudanca(campo, velhos[campo], novos[campo])
            for campo in LABELS
            if velhos[campo] != novos[campo]
        )
        if mudancas and _futuro(jogo, agora):
            eventos.append(JogoAlterado(anterior, jogo, mudancas))

    for chave, jogo in mapa_antes.items():
        if chave not in mapa_depois and _futuro(jogo, agora):
            eventos.append(JogoRemovido(jogo))

    return _ordenar(eventos)


def _ordenar(eventos: list[Evento]) -> list[Evento]:
    def chave(evento: Evento):
        inicio = evento.jogo.inicio
        return (inicio is None, inicio.timestamp() if inicio else 0, evento.jogo.id_jogo)

    return sorted(eventos, key=chave)
