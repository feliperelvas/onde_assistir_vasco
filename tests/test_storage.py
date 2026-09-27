"""Persistência do estado em data/."""

import json

from vascotv import storage


def test_ida_e_volta_preserva_os_jogos(jogos, tmp_path):
    caminho = tmp_path / "jogos.json"

    storage.salvar_snapshot(jogos, caminho)

    assert storage.carregar_snapshot(caminho) == jogos


def test_snapshot_inexistente_devolve_none(tmp_path):
    """None sinaliza primeira execução, e o `sync` depende disso."""
    assert storage.carregar_snapshot(tmp_path / "nao-existe.json") is None


def test_snapshot_vazio_e_diferente_de_inexistente(tmp_path):
    """Arquivo com zero jogos é uma linha de base válida, não primeira execução."""
    caminho = tmp_path / "vazio.json"
    storage.salvar_snapshot([], caminho)

    assert storage.carregar_snapshot(caminho) == []


def test_gravacao_e_deterministica(jogos, tmp_path):
    """Sem isso o workflow commitaria a cada execução, mesmo sem novidade."""
    a, b = tmp_path / "a.json", tmp_path / "b.json"

    storage.salvar_snapshot(jogos, a)
    storage.salvar_snapshot(list(reversed(jogos)), b)

    assert a.read_text(encoding="utf-8") != b.read_text(encoding="utf-8")
    storage.salvar_snapshot(jogos, b)
    assert a.read_text(encoding="utf-8") == b.read_text(encoding="utf-8")


def test_snapshot_nao_guarda_timestamp(jogos, tmp_path):
    """Um campo 'atualizado_em' faria o git ver mudança em toda execução."""
    caminho = tmp_path / "jogos.json"
    storage.salvar_snapshot(jogos, caminho)

    assert set(json.loads(caminho.read_text(encoding="utf-8"))) == {"jogos"}


def test_snapshot_nao_guarda_placar(jogos, tmp_path):
    caminho = tmp_path / "jogos.json"
    storage.salvar_snapshot(jogos, caminho)

    assert "gols" not in caminho.read_text(encoding="utf-8")


def test_lembretes_ida_e_volta(tmp_path):
    caminho = tmp_path / "lembretes.json"

    storage.salvar_lembretes({"2", "1"}, caminho)

    assert storage.carregar_lembretes(caminho) == {"1", "2"}
    assert json.loads(caminho.read_text(encoding="utf-8"))["enviados"] == ["1", "2"]


def test_lembretes_inexistente_devolve_conjunto_vazio(tmp_path):
    assert storage.carregar_lembretes(tmp_path / "nada.json") == set()
