"""Linha de comando: `python -m vascotv sync`, `lembrete` e `testar`."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

from . import cbf, config, render, storage, telegram
from .diff import comparar
from .filtros import jogos_do_vasco
from .models import Jogo

log = logging.getLogger("vascotv")


def _preparar_saida() -> None:
    # O console do Windows usa cp1252 por padrão e engasgaria com os emojis.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _entregar(mensagens: list[str], dry_run: bool) -> None:
    for mensagem in mensagens:
        if dry_run:
            print("\n--- mensagem que seria enviada ---")
            print(mensagem)
        else:
            telegram.enviar(mensagem)


def _resumir(jogos: list[Jogo]) -> None:
    print(f"\n{len(jogos)} jogo(s) do Vasco profissional na janela:")
    for jogo in jogos:
        print(f"  {jogo.data_hora_curta}  {jogo.confronto}")
        print(f"      {jogo.competicao} — rodada {jogo.rodada} | {jogo.local_formatado}")
        print(f"      TV: {jogo.onde_assistir}")


def comando_sync(args: argparse.Namespace) -> int:
    inicio, fim = cbf.janela_padrao()
    log.info("Buscando jogos de %s a %s", inicio, fim)
    jogos = jogos_do_vasco(cbf.buscar_todos(inicio, fim))

    anterior = storage.carregar_snapshot()
    if anterior is None:
        # Primeira execução: notificar tudo viraria um despejo do calendário
        # inteiro. Só registramos a linha de base.
        log.info("Sem snapshot anterior: gravando carga inicial, sem notificar")
        _resumir(jogos)
        if not args.dry_run:
            storage.salvar_snapshot(jogos)
        return 0

    eventos = comparar(anterior, jogos)
    if not eventos:
        log.info("Nenhuma mudanca no calendario (%d jogos)", len(jogos))
    else:
        log.info("%d evento(s) detectado(s)", len(eventos))
        _entregar(render.mensagens_eventos(eventos), args.dry_run)

    if args.dry_run:
        _resumir(jogos)
    else:
        storage.salvar_snapshot(jogos)
    return 0


def comando_lembrete(args: argparse.Namespace) -> int:
    jogos = storage.carregar_snapshot()
    if jogos is None:
        log.error("Nao existe %s. Rode `sync` antes.", config.SNAPSHOT_PATH)
        return 1

    hoje = datetime.now(config.FUSO).date()
    do_dia = [jogo for jogo in jogos if jogo.inicio and jogo.inicio.date() == hoje]
    if not do_dia:
        log.info("Nenhum jogo do Vasco hoje (%s)", hoje)
        return 0

    enviados = storage.carregar_lembretes()
    pendentes = [jogo for jogo in do_dia if jogo.id_jogo not in enviados]
    if not pendentes:
        log.info("Lembrete de hoje ja foi enviado; nada a fazer")
        return 0

    _entregar([render.mensagem_lembrete(pendentes)], args.dry_run)

    if not args.dry_run:
        # Só IDs ainda presentes no snapshot, para o arquivo não crescer sem fim.
        vigentes = {jogo.id_jogo for jogo in jogos}
        atualizados = (enviados | {jogo.id_jogo for jogo in pendentes}) & vigentes
        storage.salvar_lembretes(atualizados)
    return 0


def comando_testar(args: argparse.Namespace) -> int:
    # Prova que token e chat_id funcionam sem depender de o calendário mudar.
    agora = datetime.now(config.FUSO).strftime("%d/%m %H:%M")
    _entregar([f"✅ Teste do monitor do Vasco ({agora}). O envio está funcionando."], args.dry_run)
    return 0


def construir_parser() -> argparse.ArgumentParser:
    # Parent parser para que --dry-run funcione depois do subcomando, que e a
    # forma que a pessoa naturalmente digita: `vascotv sync --dry-run`.
    comuns = argparse.ArgumentParser(add_help=False)
    comuns.add_argument(
        "--dry-run",
        action="store_true",
        help="mostra no terminal em vez de enviar ao Telegram; nao grava estado",
    )

    parser = argparse.ArgumentParser(
        prog="vascotv",
        description="Monitora onde assistir os jogos do Vasco no site da CBF.",
        parents=[comuns],
    )
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser(
        "sync",
        parents=[comuns],
        help="busca o calendario, detecta mudancas e notifica",
    )
    sub.add_parser("lembrete", parents=[comuns], help="avisa sobre os jogos de hoje")
    sub.add_parser("testar", parents=[comuns], help="envia uma mensagem de teste ao Telegram")
    return parser


def main(argv: list[str] | None = None) -> int:
    _preparar_saida()
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )

    args = construir_parser().parse_args(argv)
    acoes = {"sync": comando_sync, "lembrete": comando_lembrete, "testar": comando_testar}
    try:
        return acoes[args.comando](args)
    except (cbf.ErroCBF, telegram.ErroTelegram) as erro:
        log.error("%s", erro)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
