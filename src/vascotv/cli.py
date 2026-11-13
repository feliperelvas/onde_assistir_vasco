"""Linha de comando: `python -m vascotv sync`, `lembrete`, `semana` e `testar`."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from datetime import date, datetime, timedelta

from . import cbf, config, fotmob, render, storage, telegram
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
        print(f"      {jogo.competicao} — {jogo.etapa} | {jogo.local_formatado}")
        print(f"      TV: {jogo.onde_assistir}")


FONTE_FOTMOB = "FotMob"


def _do_fotmob(jogo: Jogo) -> bool:
    return jogo.id_jogo.startswith("fotmob-")


def _manter_transmissoes(novos: list[Jogo], anteriores: list[Jogo]) -> list[Jogo]:
    """O guia de TV do FotMob só cobre 7 dias a partir de hoje.

    Sem isto, o jogo que acabou de sair do guia (ou que sumiu dele por um
    soluço) perderia os canais e geraria um aviso falso de transmissão.
    """
    canais = {jogo.id_jogo: jogo.transmissoes for jogo in anteriores}
    return [
        replace(jogo, transmissoes=canais[jogo.id_jogo])
        if not jogo.transmissoes and canais.get(jogo.id_jogo)
        else jogo
        for jogo in novos
    ]


def _buscar_fotmob(
    inicio, fim, anterior: list[Jogo], da_cbf: list[Jogo]
) -> tuple[list[Jogo], str | None]:
    """Jogos do FotMob e o erro, se houve.

    Diferente da CBF, falha aqui não aborta o run: o FotMob não é oficial e pode
    bloquear a qualquer hora, e isso não pode derrubar Brasileirão e Copa do
    Brasil. Os jogos dele ficam como estavam no snapshot — sem isso seriam
    anunciados como "saiu do calendário".
    """
    try:
        do_fotmob = fotmob.buscar_todos(inicio, fim, da_cbf=da_cbf)
        return _manter_transmissoes(do_fotmob, anterior), None
    except fotmob.ErroFotMob as erro:
        log.error("FotMob: %s", erro)
        return [jogo for jogo in anterior if _do_fotmob(jogo)], str(erro)


def _rodada_cbf(jogo: Jogo) -> tuple[str, int, str] | None:
    """Identifica o jogo de liga por rodada, para casar CBF e FotMob.

    O ano separa temporadas: a janela de 400 dias pega a tabela do ano seguinte
    assim que a CBF publica, e a rodada 21 de lá não é a de agora.
    """
    complementares = {c[0]: c[2] for c in config.FOTMOB_COMPLEMENTO.values()}
    if (
        complementares.get(jogo.campeonato_id) != jogo.categoria_id
        or not jogo.rodada.isdigit()
        or jogo.inicio is None
        or config.VASCO_ID not in (jogo.mandante.id, jogo.visitante.id)
    ):
        return None
    return (jogo.campeonato_id, jogo.inicio.year, jogo.rodada)


def _unir_fontes(
    da_cbf: list[Jogo], do_fotmob: list[Jogo], anterior: list[Jogo]
) -> tuple[list[Jogo], dict[str, Jogo]]:
    """Junta as fontes; a CBF manda quando as duas têm a mesma rodada.

    Devolve também {id do FotMob -> jogo da CBF} para o jogo que já estava no
    snapshot pelo FotMob e agora a CBF publicou: é o mesmo jogo trocando de
    fonte, não um que saiu e outro que entrou.
    """
    da_cbf_por_rodada = {}
    for jogo in da_cbf:
        chave = _rodada_cbf(jogo)
        if chave:
            da_cbf_por_rodada[chave] = jogo
    completos = [
        jogo for jogo in do_fotmob if _rodada_cbf(jogo) not in da_cbf_por_rodada
    ]
    trocas = {
        jogo.id_jogo: da_cbf_por_rodada[chave]
        for jogo in anterior
        if _do_fotmob(jogo) and (chave := _rodada_cbf(jogo)) in da_cbf_por_rodada
    }
    return da_cbf + completos, trocas


def _como_na_cbf(antigo: Jogo, da_cbf: Jogo) -> Jogo:
    """A versão do FotMob no snapshot, reescrita com a grafia da CBF.

    Nome de time, estádio e caixa dos canais variam entre as fontes ("RB
    Bragantino", "SporTV"); sem isto a troca de fonte viraria aviso de mudança.
    Data, hora e canais diferentes de verdade continuam sendo avisados.
    """
    def canais(jogo: Jogo) -> set[str]:
        return {canal.casefold() for canal in jogo.transmissoes}

    mesmos_canais = canais(antigo) == canais(da_cbf)
    return replace(
        da_cbf,
        data=antigo.data,
        hora=antigo.hora,
        transmissoes=da_cbf.transmissoes if mesmos_canais else antigo.transmissoes,
    )


def _avisar_fonte(fonte: str, erro: str | None, dry_run: bool) -> None:
    """Avisa só na mudança de estado: quando quebra e quando volta."""
    alertas = storage.carregar_alertas()
    if erro and fonte not in alertas:
        _entregar([render.mensagem_fonte_com_problema(fonte, erro)], dry_run)
        alertas[fonte] = erro
    elif not erro and fonte in alertas:
        _entregar([render.mensagem_fonte_voltou(fonte)], dry_run)
        del alertas[fonte]
    else:
        return
    if not dry_run:
        storage.salvar_alertas(alertas)


def comando_sync(args: argparse.Namespace) -> int:
    inicio, fim = cbf.janela_padrao()
    log.info("Buscando jogos de %s a %s", inicio, fim)
    # Falha da CBF aborta o run (ErroCBF sobe até main); a do FotMob, não.
    da_cbf = cbf.buscar_todos(inicio, fim)
    anterior = storage.carregar_snapshot()
    do_fotmob, erro_fotmob = _buscar_fotmob(inicio, fim, anterior or [], da_cbf)
    unidos, trocas = _unir_fontes(da_cbf, do_fotmob, anterior or [])
    jogos = jogos_do_vasco(unidos)
    _avisar_fonte(FONTE_FOTMOB, erro_fotmob, args.dry_run)
    if trocas:
        log.info(
            "Passaram do FotMob para a CBF: %s",
            {antigo: novo.id_jogo for antigo, novo in trocas.items()},
        )
        anterior = [
            _como_na_cbf(jogo, trocas[jogo.id_jogo]) if jogo.id_jogo in trocas else jogo
            for jogo in anterior
        ]
        # O lembrete já enviado pelo id do FotMob vale para o id da CBF.
        enviados = storage.carregar_lembretes()
        herdados = {trocas[i].id_jogo for i in enviados & trocas.keys()}
        if herdados and not args.dry_run:
            storage.salvar_lembretes(enviados | herdados)

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


def _hoje() -> date:
    return datetime.now(config.FUSO).date()


def _jogos_da_semana(jogos: list[Jogo], hoje: date) -> tuple[list[Jogo], date, date]:
    """Jogos de segunda a domingo da semana de `hoje`, em ordem cronológica."""
    segunda = hoje - timedelta(days=hoje.weekday())
    domingo = segunda + timedelta(days=6)
    da_semana = [j for j in jogos if j.inicio and segunda <= j.inicio.date() <= domingo]
    return sorted(da_semana, key=lambda j: j.inicio), segunda, domingo


def _resumo_semanal(jogos: list[Jogo], hoje: date, dry_run: bool) -> None:
    """Na segunda, uma vez por semana: os mesmos 3 crons do lembrete chamam
    isto, e data/resumo_semanal.json impede que os reservas repitam."""
    if hoje.weekday() != 0:
        return
    da_semana, segunda, domingo = _jogos_da_semana(jogos, hoje)
    if storage.carregar_ultimo_resumo() == segunda.isoformat():
        log.info("Resumo da semana ja foi enviado")
        return
    _entregar(render.mensagens_resumo_semanal(da_semana, segunda, domingo), dry_run)
    if not dry_run:
        storage.salvar_ultimo_resumo(segunda.isoformat())


def _carregar_ou_avisar() -> list[Jogo] | None:
    jogos = storage.carregar_snapshot()
    if jogos is None:
        log.error("Nao existe %s. Rode `sync` antes.", config.SNAPSHOT_PATH)
    return jogos


def comando_lembrete(args: argparse.Namespace) -> int:
    jogos = _carregar_ou_avisar()
    if jogos is None:
        return 1

    hoje = _hoje()
    # Antes do lembrete do dia: a visão da semana vem primeiro no chat.
    _resumo_semanal(jogos, hoje, args.dry_run)

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


def comando_semana(args: argparse.Namespace) -> int:
    """Resumo da semana atual sob demanda, em qualquer dia; não mexe no estado."""
    jogos = _carregar_ou_avisar()
    if jogos is None:
        return 1
    da_semana, segunda, domingo = _jogos_da_semana(jogos, _hoje())
    _entregar(render.mensagens_resumo_semanal(da_semana, segunda, domingo), args.dry_run)
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
        description="Monitora onde assistir os jogos do Vasco (CBF e FotMob).",
        parents=[comuns],
    )
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser(
        "sync",
        parents=[comuns],
        help="busca o calendario, detecta mudancas e notifica",
    )
    sub.add_parser(
        "lembrete",
        parents=[comuns],
        help="avisa sobre os jogos de hoje (e, na segunda, os da semana)",
    )
    sub.add_parser("semana", parents=[comuns], help="envia os jogos desta semana (seg a dom)")
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
    acoes = {
        "sync": comando_sync,
        "lembrete": comando_lembrete,
        "semana": comando_semana,
        "testar": comando_testar,
    }
    try:
        return acoes[args.comando](args)
    except (cbf.ErroCBF, telegram.ErroTelegram) as erro:
        log.error("%s", erro)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
