"""Comportamento dos comandos, com a API e o Telegram substituídos."""

from datetime import datetime

import pytest

from vascotv import cbf, cli, config, storage, telegram


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    """Redireciona o estado para tmp_path e captura o que iria ao Telegram."""
    enviadas: list[str] = []
    monkeypatch.setattr(config, "SNAPSHOT_PATH", tmp_path / "jogos.json")
    monkeypatch.setattr(config, "LEMBRETES_PATH", tmp_path / "lembretes.json")
    monkeypatch.setattr(telegram, "enviar", lambda texto, **kw: enviadas.append(texto))
    return enviadas


def _com_api(monkeypatch, jogos):
    monkeypatch.setattr(cbf, "buscar_todos", lambda *a, **kw: list(jogos))


# --- sync -------------------------------------------------------------------
def test_primeira_execucao_grava_sem_notificar(ambiente, monkeypatch, jogos):
    """Notificar na carga inicial despejaria o calendário inteiro no chat."""
    _com_api(monkeypatch, jogos)

    assert cli.main(["sync"]) == 0

    assert ambiente == []
    assert len(storage.carregar_snapshot()) == 2


def test_sync_sem_mudanca_fica_calado(ambiente, monkeypatch, jogos):
    _com_api(monkeypatch, jogos)
    cli.main(["sync"])

    assert cli.main(["sync"]) == 0
    assert ambiente == []


def test_sync_notifica_horario_remarcado(ambiente, monkeypatch, jogos, fazer_jogo):
    _com_api(monkeypatch, jogos)
    cli.main(["sync"])

    remarcado = [
        fazer_jogo(hora="21:30") if j.id_jogo == "832172" else j
        for j in storage.carregar_snapshot()
    ]
    monkeypatch.setattr(cbf, "buscar_todos", lambda *a, **kw: remarcado)

    assert cli.main(["sync"]) == 0

    (mensagem,) = ambiente
    assert "20:30</s> → <b>21:30" in mensagem


def test_dry_run_nao_envia_nem_grava(ambiente, monkeypatch, jogos, fazer_jogo):
    _com_api(monkeypatch, jogos)
    cli.main(["sync"])
    antes = config.SNAPSHOT_PATH.read_text(encoding="utf-8")

    monkeypatch.setattr(cbf, "buscar_todos", lambda *a, **kw: [fazer_jogo(hora="21:30")])
    assert cli.main(["sync", "--dry-run"]) == 0

    assert ambiente == []
    assert config.SNAPSHOT_PATH.read_text(encoding="utf-8") == antes


def test_falha_da_api_devolve_codigo_de_erro(ambiente, monkeypatch):
    def explode(*a, **kw):
        raise cbf.ErroCBF("API fora do ar")

    monkeypatch.setattr(cbf, "buscar_todos", explode)

    assert cli.main(["sync"]) == 1


def test_falha_no_envio_preserva_o_snapshot_antigo(ambiente, monkeypatch, jogos, fazer_jogo):
    """Se a mensagem não saiu, o snapshot não pode avançar: senão o aviso se perde
    para sempre e a próxima execução acharia que nada mudou."""
    _com_api(monkeypatch, jogos)
    cli.main(["sync"])
    antes = config.SNAPSHOT_PATH.read_text(encoding="utf-8")

    def falha(*a, **kw):
        raise telegram.ErroTelegram("Telegram fora do ar")

    monkeypatch.setattr(telegram, "enviar", falha)
    monkeypatch.setattr(cbf, "buscar_todos", lambda *a, **kw: [fazer_jogo(hora="21:30")])

    assert cli.main(["sync"]) == 1
    assert config.SNAPSHOT_PATH.read_text(encoding="utf-8") == antes


# --- lembrete ---------------------------------------------------------------
@pytest.fixture
def jogo_de_hoje(fazer_jogo):
    hoje = datetime.now(config.FUSO).date()
    return fazer_jogo(data=hoje.strftime("%d/%m/%Y"))


def test_lembrete_avisa_o_jogo_de_hoje(ambiente, jogo_de_hoje):
    storage.salvar_snapshot([jogo_de_hoje])

    assert cli.main(["lembrete"]) == 0

    (mensagem,) = ambiente
    assert "Hoje tem Vasco" in mensagem
    assert "Botafogo x Vasco" in mensagem


def test_lembrete_nao_repete(ambiente, jogo_de_hoje):
    """Idempotência: o cron pode disparar duas vezes, ou eu rodar na mão."""
    storage.salvar_snapshot([jogo_de_hoje])
    cli.main(["lembrete"])

    assert cli.main(["lembrete"]) == 0
    assert len(ambiente) == 1


def test_lembrete_calado_quando_nao_tem_jogo(ambiente, fazer_jogo):
    storage.salvar_snapshot([fazer_jogo(data="07/10/2099")])

    assert cli.main(["lembrete"]) == 0
    assert ambiente == []


def test_lembrete_sem_snapshot_falha_com_clareza(ambiente):
    assert cli.main(["lembrete"]) == 1
    assert ambiente == []


def test_lembrete_dry_run_nao_marca_como_enviado(ambiente, jogo_de_hoje):
    storage.salvar_snapshot([jogo_de_hoje])

    cli.main(["lembrete", "--dry-run"])

    assert storage.carregar_lembretes() == set()


def test_lembretes_antigos_sao_podados(ambiente, jogo_de_hoje, fazer_jogo):
    """O arquivo não pode crescer para sempre."""
    storage.salvar_lembretes({"id-de-temporada-passada"})
    storage.salvar_snapshot([jogo_de_hoje])

    cli.main(["lembrete"])

    assert storage.carregar_lembretes() == {jogo_de_hoje.id_jogo}


# --- testar -----------------------------------------------------------------
def test_testar_envia_uma_mensagem_sem_tocar_api_nem_estado(ambiente, monkeypatch):
    def api_proibida(*a, **kw):
        raise AssertionError("testar não deve consultar a CBF")

    monkeypatch.setattr(cbf, "buscar_todos", api_proibida)

    assert cli.main(["testar"]) == 0

    (mensagem,) = ambiente
    assert "Teste do monitor do Vasco" in mensagem
    assert not config.SNAPSHOT_PATH.exists()


def test_testar_dry_run_nao_envia(ambiente, capsys):
    assert cli.main(["testar", "--dry-run"]) == 0

    assert ambiente == []
    assert "Teste do monitor do Vasco" in capsys.readouterr().out
