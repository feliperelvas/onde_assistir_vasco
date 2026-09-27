"""Montagem das mensagens do Telegram (parse_mode=HTML)."""

from __future__ import annotations

from html import escape

from .diff import Evento, JogoAlterado, JogoNovo, JogoRemovido
from .filtros import categoria_incerta
from .models import Jogo

# O limite do Telegram é 4096 caracteres; sobra folga para o cabeçalho.
LIMITE = 3500

AVISO_CATEGORIA = (
    "⚠️ Categoria <code>{}</code> desconhecida — confira se é mesmo o profissional."
)


def _ficha(jogo: Jogo, com_data: bool = True) -> list[str]:
    linhas = [
        f"⚽ <b>{escape(jogo.confronto)}</b>",
        f"🏆 {escape(jogo.competicao)} — rodada {escape(jogo.rodada)}",
    ]
    if com_data:
        linhas.append(f"🕐 {escape(jogo.data_hora_curta)}")
    linhas.append(f"🏟 {escape(jogo.local_formatado)}")
    linhas.append(f"📺 {escape(jogo.onde_assistir)}")
    if categoria_incerta(jogo):
        linhas.append(AVISO_CATEGORIA.format(escape(jogo.categoria_id)))
    return linhas


def bloco_evento(evento: Evento) -> str:
    if isinstance(evento, JogoNovo):
        return "\n".join(["🆕 <b>Jogo novo no calendário</b>", *_ficha(evento.jogo)])

    if isinstance(evento, JogoRemovido):
        jogo = evento.jogo
        return "\n".join(
            [
                "❌ <b>Jogo saiu do calendário</b>",
                f"⚽ <b>{escape(jogo.confronto)}</b>",
                f"🏆 {escape(jogo.competicao)} — rodada {escape(jogo.rodada)}",
                f"🕐 estava marcado para {escape(jogo.data_hora_curta)}",
            ]
        )

    if isinstance(evento, JogoAlterado):
        jogo = evento.depois
        linhas = [
            f"🔔 <b>{escape(jogo.confronto)}</b>",
            f"🏆 {escape(jogo.competicao)} — rodada {escape(jogo.rodada)}",
        ]
        for mudanca in evento.mudancas:
            de = escape(mudanca.de) or "—"
            para = escape(mudanca.para) or "—"
            linhas.append(f"• {mudanca.label}: <s>{de}</s> → <b>{para}</b>")
        linhas.append(f"🕐 {escape(jogo.data_hora_curta)}")
        if categoria_incerta(jogo):
            linhas.append(AVISO_CATEGORIA.format(escape(jogo.categoria_id)))
        return "\n".join(linhas)

    raise TypeError(f"Evento não suportado: {evento!r}")


def mensagens_eventos(eventos: list[Evento]) -> list[str]:
    """Agrupa os eventos em mensagens, quebrando antes de estourar o limite."""
    if not eventos:
        return []

    cabecalho = "🔔 <b>Calendário do Vasco atualizado</b>"
    mensagens: list[str] = []
    atual = [cabecalho]
    tamanho = len(cabecalho)

    for evento in eventos:
        bloco = bloco_evento(evento)
        if len(atual) > 1 and tamanho + len(bloco) + 2 > LIMITE:
            mensagens.append("\n\n".join(atual))
            atual = [cabecalho]
            tamanho = len(cabecalho)
        atual.append(bloco)
        tamanho += len(bloco) + 2

    if len(atual) > 1:
        mensagens.append("\n\n".join(atual))
    return mensagens


def mensagem_lembrete(jogos: list[Jogo]) -> str:
    """Lembrete da manhã do dia do jogo."""
    if not jogos:
        raise ValueError("mensagem_lembrete precisa de ao menos um jogo")

    titulo = (
        "📅 <b>Hoje tem Vasco!</b>"
        if len(jogos) == 1
        else f"📅 <b>Hoje tem Vasco ({len(jogos)} jogos)</b>"
    )
    blocos = [titulo]
    for jogo in jogos:
        linhas = [
            f"⚽ <b>{escape(jogo.confronto)}</b>",
            f"🏆 {escape(jogo.competicao)} — rodada {escape(jogo.rodada)}",
            f"🕐 {escape(jogo.hora)} (horário de Brasília)",
            f"🏟 {escape(jogo.local_formatado)}",
            f"📺 {escape(jogo.onde_assistir)}",
        ]
        if categoria_incerta(jogo):
            linhas.append(AVISO_CATEGORIA.format(escape(jogo.categoria_id)))
        blocos.append("\n".join(linhas))
    return "\n\n".join(blocos)
