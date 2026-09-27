"""O filtro que separa o profissional da base — a regra mais fácil de errar."""

from vascotv import config
from vascotv.filtros import Classificacao, classificar, envolve_vasco, jogos_do_vasco


def test_seleciona_apenas_o_profissional_do_vasco(jogos):
    selecionados = jogos_do_vasco(jogos)

    assert [(j.confronto, j.categoria_nome) for j in selecionados] == [
        ("Botafogo x Vasco", "Série A"),
        ("Vasco x Remo", "Série A"),
    ]


def test_descarta_base_mesmo_com_o_id_do_vasco(jogos):
    """Sub-20 e SUB17 usam o mesmo id do profissional; só a categoria separa."""
    descartados = [
        j for j in jogos if envolve_vasco(j) and j not in jogos_do_vasco(jogos)
    ]

    assert {j.categoria_nome for j in descartados} == {"SUB17", "Sub-20"}
    assert all(j.visitante.id == config.VASCO_ID or j.mandante.id == config.VASCO_ID
               for j in descartados)


def test_ignora_jogos_sem_o_vasco(jogos):
    assert not any(
        "Criciúma" in j.confronto or "Brusque" in j.confronto for j in jogos_do_vasco(jogos)
    )


def test_categoria_desconhecida_entra_e_e_sinalizada(fazer_jogo):
    """Diante de uma categoria nova, incluir e avisar é melhor que perder o jogo."""
    jogo = fazer_jogo(
        competicao={
            "campeonato_id": "42",
            "campeonato_nome": "Campeonato Brasileiro",
            "categoria_id": "999",
            "categoria_nome": "Categoria Nova",
        }
    )

    assert classificar(jogo) is Classificacao.DESCONHECIDA
    assert jogos_do_vasco([jogo]) == [jogo]


def test_serie_b_continua_sendo_profissional(fazer_jogo):
    """Se o Vasco cair, a allowlist tem de continuar valendo."""
    jogo = fazer_jogo(
        competicao={
            "campeonato_id": "42",
            "campeonato_nome": "Campeonato Brasileiro",
            "categoria_id": "2",
            "categoria_nome": "Série B",
        }
    )

    assert classificar(jogo) is Classificacao.PROFISSIONAL


def test_ordena_por_inicio(jogos):
    selecionados = jogos_do_vasco(jogos)
    assert [j.inicio for j in selecionados] == sorted(j.inicio for j in selecionados)
