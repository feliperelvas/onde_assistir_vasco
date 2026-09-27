"""Envio de mensagens pelo Telegram Bot API."""

from __future__ import annotations

import logging
import os

import requests

log = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/sendMessage"
TIMEOUT = 30


class ErroTelegram(RuntimeError):
    """Não foi possível entregar a mensagem."""


def credenciais() -> tuple[str, str]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    faltando = [
        nome
        for nome, valor in (("TELEGRAM_BOT_TOKEN", token), ("TELEGRAM_CHAT_ID", chat_id))
        if not valor
    ]
    if faltando:
        raise ErroTelegram(f"Variáveis de ambiente ausentes: {', '.join(faltando)}")
    return token, chat_id


def enviar(texto: str, token: str | None = None, chat_id: str | None = None) -> None:
    if token is None or chat_id is None:
        token, chat_id = credenciais()

    resposta = requests.post(
        API.format(token=token),
        json={
            "chat_id": chat_id,
            "text": texto,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=TIMEOUT,
    )
    if not resposta.ok:
        # A URL carrega o token: nunca deixe `resposta.url` vazar para o log.
        detalhe = ""
        try:
            detalhe = resposta.json().get("description", "")
        except ValueError:
            detalhe = resposta.text[:200]
        raise ErroTelegram(f"Telegram respondeu HTTP {resposta.status_code}: {detalhe}")
    log.info("Mensagem enviada (%d caracteres)", len(texto))
