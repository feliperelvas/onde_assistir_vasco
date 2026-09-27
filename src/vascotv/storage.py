"""Leitura e escrita do estado versionado em data/.

O JSON é gravado de forma determinística (chaves ordenadas, sem timestamp) para
que o `git diff` mostre apenas o que realmente mudou no calendário — é isso que
permite ao workflow commitar somente quando há novidade.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import config
from .models import Jogo


def _escrever(caminho: Path, dados) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(dados, ensure_ascii=False, indent=2, sort_keys=True)
    caminho.write_text(texto + "\n", encoding="utf-8")


def carregar_snapshot(caminho: Path | None = None) -> list[Jogo] | None:
    """Jogos do snapshot, ou None se ainda não existe (primeira execução)."""
    caminho = caminho or config.SNAPSHOT_PATH
    if not caminho.exists():
        return None
    bruto = json.loads(caminho.read_text(encoding="utf-8"))
    return [Jogo.from_dict(item) for item in bruto.get("jogos", [])]


def salvar_snapshot(jogos: list[Jogo], caminho: Path | None = None) -> None:
    caminho = caminho or config.SNAPSHOT_PATH
    _escrever(caminho, {"jogos": [jogo.to_dict() for jogo in jogos]})


def carregar_lembretes(caminho: Path | None = None) -> set[str]:
    caminho = caminho or config.LEMBRETES_PATH
    if not caminho.exists():
        return set()
    bruto = json.loads(caminho.read_text(encoding="utf-8"))
    return set(bruto.get("enviados", []))


def salvar_lembretes(ids: set[str], caminho: Path | None = None) -> None:
    caminho = caminho or config.LEMBRETES_PATH
    _escrever(caminho, {"enviados": sorted(ids)})
