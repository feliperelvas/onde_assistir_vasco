"""Detecção de mudanças: o núcleo do projeto."""

from datetime import datetime

from vascotv import config
from vascotv.diff import JogoAlterado, JogoNovo, JogoRemovido, comparar


def test_sem_mudanca_nao_gera_evento(fazer_jogo, agora):
    jogo = fazer_jogo()
    assert comparar([jogo], [jogo], agora) == []


def test_horario_remarcado(fazer_jogo, agora):
    eventos = comparar([fazer_jogo()], [fazer_jogo(hora="21:30")], agora)

    (evento,) = eventos
    assert isinstance(evento, JogoAlterado)
    assert [(m.label, m.de, m.para) for m in evento.mudancas] == [("horário", "20:30", "21:30")]


def test_troca_de_transmissao(fazer_jogo, agora):
    depois = fazer_jogo(transmissoes=[{"nome": "Globo"}, {"nome": "Premiere"}])
    (evento,) = comparar([fazer_jogo()], [depois], agora)

    assert [(m.label, m.de, m.para) for m in evento.mudancas] == [
        ("transmissão", "Amazon Prime", "Globo, Premiere")
    ]


def test_transmissao_reordenada_nao_gera_evento(fazer_jogo, agora):
    """A API não garante ordem; comparar a lista crua daria alarme falso."""
    antes = fazer_jogo(transmissoes=[{"nome": "Globo"}, {"nome": "Premiere"}])
    depois = fazer_jogo(transmissoes=[{"nome": "Premiere"}, {"nome": "Globo"}])

    assert comparar([antes], [depois], agora) == []


def test_placar_preenchido_nao_gera_evento(fazer_jogo, agora):
    """Durante o jogo o placar muda; notificar cada gol seria spam."""
    antes = fazer_jogo(mandante={"id": "20003", "nome": "Botafogo", "url_escudo": "", "gols": None})
    depois = fazer_jogo(mandante={"id": "20003", "nome": "Botafogo", "url_escudo": "", "gols": "2"})

    assert comparar([antes], [depois], agora) == []


def test_jogo_novo_no_futuro(fazer_jogo, agora):
    (evento,) = comparar([], [fazer_jogo()], agora)
    assert isinstance(evento, JogoNovo)


def test_jogo_removido_do_futuro(fazer_jogo, agora):
    (evento,) = comparar([fazer_jogo()], [], agora)
    assert isinstance(evento, JogoRemovido)


def test_jogo_passado_que_sai_da_janela_nao_vira_removido(fazer_jogo, agora):
    """A janela começa em hoje − 7 dias: jogo antigo desaparece naturalmente."""
    antigo = fazer_jogo(data="01/03/2026")
    assert comparar([antigo], [], agora) == []


def test_mudanca_em_jogo_ja_disputado_e_ignorada(fazer_jogo, agora):
    antigo = fazer_jogo(data="01/03/2026")
    corrigido = fazer_jogo(data="01/03/2026", hora="22:00")

    assert comparar([antigo], [corrigido], agora) == []


def test_adiamento_para_o_futuro_e_anunciado(fazer_jogo):
    """Jogo de ontem remarcado para o mês que vem tem de gerar aviso."""
    agora = datetime(2026, 10, 8, 10, 0, tzinfo=config.FUSO)
    antes = fazer_jogo(data="07/10/2026")
    depois = fazer_jogo(data="20/11/2026")

    (evento,) = comparar([antes], [depois], agora)
    assert [m.label for m in evento.mudancas] == ["data"]


def test_multiplas_mudancas_no_mesmo_jogo(fazer_jogo, agora):
    depois = fazer_jogo(
        hora="16:00", local="Maracanã - Rio de Janeiro - RJ", transmissoes=[{"nome": "Globo"}]
    )
    (evento,) = comparar([fazer_jogo()], [depois], agora)

    assert [m.label for m in evento.mudancas] == ["horário", "local", "transmissão"]


def test_eventos_saem_ordenados_por_data(fazer_jogo, agora):
    tarde = fazer_jogo(id_jogo="2", data="20/10/2026")
    cedo = fazer_jogo(id_jogo="3", data="09/10/2026")

    eventos = comparar([], [tarde, cedo], agora)
    assert [e.jogo.id_jogo for e in eventos] == ["3", "2"]


def test_data_ilegivel_e_tratada_como_relevante(fazer_jogo, agora):
    """Falhar alto: melhor avisar do que engolir um dado estranho."""
    (evento,) = comparar([], [fazer_jogo(data="a definir")], agora)
    assert isinstance(evento, JogoNovo)
