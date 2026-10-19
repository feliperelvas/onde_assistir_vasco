"""Quanto esperar entre tentativas de uma requisição."""

from __future__ import annotations

from . import config


def espera(erro: Exception, tentativa: int) -> float:
    """Segundos até a próxima tentativa.

    Backoff exponencial curto para falha de rede e 5xx. HTTP 429 (limite de
    requisições) espera mais: o Retry-After do servidor, se vier em segundos, ou
    um backoff a partir de ESPERA_429 — sempre limitado a ESPERA_MAXIMA, para
    não prender o runner.
    """
    resposta = getattr(erro, "response", None)
    if resposta is None or resposta.status_code != 429:
        return 2**tentativa
    try:
        pedida = float(resposta.headers.get("Retry-After", ""))
    except (TypeError, ValueError):
        # Ausente ou no formato de data HTTP: segue o backoff próprio.
        pedida = config.ESPERA_429 * 2**tentativa
    return min(max(pedida, 1), config.ESPERA_MAXIMA)
