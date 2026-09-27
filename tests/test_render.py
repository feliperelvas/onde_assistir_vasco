"""Formatação das mensagens do Telegram."""

import pytest

from vascotv import render
from vascotv.diff import comparar
from vascotv.filtros import jogos_do_vasco
from vascotv.models import formatar_local


def test_lembrete_traz_tudo_que_importa(jogos):
    do_dia = [j for j in jogos_do_vasco(jogos) if j.data == "10/10/2026"]

    texto = render.mensagem_lembrete(do_dia)

    assert "Hoje tem Vasco!" in texto
    assert "Vasco x Remo" in texto
    assert "17:00" in texto
    assert "São Januário — Rio de Janeiro, RJ" in texto
    assert "Premiere, Record, YouTube / Cazé TV" in texto


def test_lembrete_com_dois_jogos_ajusta_o_titulo(jogos):
    texto = render.mensagem_lembrete(jogos_do_vasco(jogos))
    assert "2 jogos" in texto


def test_lembrete_sem_jogo_e_erro_de_programacao():
    """O CLI já filtra antes de chamar; um título de "0 jogos" seria silencioso."""
    with pytest.raises(ValueError):
        render.mensagem_lembrete([])


def test_mensagem_de_mudanca_mostra_de_para(fazer_jogo, agora):
    eventos = comparar([fazer_jogo()], [fazer_jogo(hora="21:30")], agora)

    (texto,) = render.mensagens_eventos(eventos)

    assert "Calendário do Vasco atualizado" in texto
    assert "<s>20:30</s> → <b>21:30</b>" in texto
    assert "Botafogo x Vasco" in texto


def test_jogo_novo_lista_a_ficha_completa(fazer_jogo, agora):
    (texto,) = render.mensagens_eventos(comparar([], [fazer_jogo()], agora))

    assert "Jogo novo no calendário" in texto
    assert "Nilton Santos — Rio de Janeiro, RJ" in texto
    assert "Amazon Prime" in texto


def test_jogo_removido(fazer_jogo, agora):
    (texto,) = render.mensagens_eventos(comparar([fazer_jogo()], [], agora))
    assert "saiu do calendário" in texto


def test_sem_eventos_nao_gera_mensagem():
    assert render.mensagens_eventos([]) == []


def test_escapa_html_vindo_da_api(fazer_jogo, agora):
    """Nome de time com '&' ou '<' não pode quebrar o parse_mode=HTML."""
    jogo = fazer_jogo(mandante={"id": "1", "nome": "A & B <Clube>", "url_escudo": ""})

    (texto,) = render.mensagens_eventos(comparar([], [jogo], agora))

    assert "A &amp; B &lt;Clube&gt;" in texto
    assert "<Clube>" not in texto


def test_jogo_sem_transmissao(fazer_jogo, agora):
    (texto,) = render.mensagens_eventos(comparar([], [fazer_jogo(transmissoes=[])], agora))
    assert "Não informado" in texto


def test_categoria_desconhecida_vira_aviso_na_mensagem(fazer_jogo, agora):
    jogo = fazer_jogo(
        competicao={
            "campeonato_id": "42",
            "campeonato_nome": "Campeonato Brasileiro",
            "categoria_id": "999",
            "categoria_nome": "Nova",
        }
    )
    (texto,) = render.mensagens_eventos(comparar([], [jogo], agora))

    assert "desconhecida" in texto
    assert "999" in texto


def test_quebra_em_varias_mensagens_no_limite(fazer_jogo, agora):
    muitos = [fazer_jogo(id_jogo=str(i), data="20/10/2026") for i in range(60)]

    mensagens = render.mensagens_eventos(comparar([], muitos, agora))

    assert len(mensagens) > 1
    assert all(len(m) <= render.LIMITE + 200 for m in mensagens)
    assert all("Calendário do Vasco atualizado" in m for m in mensagens)


def test_formatar_local_tolera_formatos_inesperados():
    assert formatar_local("Maracanã") == "Maracanã"
    assert formatar_local("Arena - SP") == "Arena — SP"
    assert formatar_local("Nilton Santos - Rio de Janeiro - RJ") == (
        "Nilton Santos — Rio de Janeiro, RJ"
    )
