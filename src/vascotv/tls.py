"""Cadeia de certificados para falar com www.cbf.com.br.

O servidor da CBF é mal configurado: o certificado dele é emitido por
"Sectigo Public Server Authentication CA OV R36", mas esse intermediário **não é
enviado** no handshake (a cadeia que chega traz outros intermediários, que não
servem). O Windows disfarça o problema porque busca o certificado que falta pela
extensão AIA; OpenSSL — e portanto o runner Ubuntu do GitHub Actions — não faz
isso e a verificação falha com CERTIFICATE_VERIFY_FAILED.

A correção é fornecer o intermediário nós mesmos: `certs/` guarda o PEM baixado
de crt.sectigo.com (válido até 2036) e aqui ele é concatenado ao bundle do
certifi. A verificação segue completa; nada de `verify=False`.
"""

from __future__ import annotations

import logging
import tempfile
from functools import lru_cache
from pathlib import Path

import certifi

from . import config

log = logging.getLogger(__name__)

INTERMEDIARIO = config.ROOT / "certs" / "sectigo-public-server-auth-ov-r36.pem"


@lru_cache(maxsize=1)
def ca_bundle() -> str:
    """Caminho de um bundle = certifi + o intermediário que a CBF não manda.

    Se o PEM extra não estiver no repo, cai no certifi puro: a conexão pode
    falhar, mas com erro claro de TLS em vez de um comportamento estranho.
    """
    if not INTERMEDIARIO.exists():
        log.warning("Intermediário %s ausente; usando apenas o certifi", INTERMEDIARIO)
        return certifi.where()

    destino = Path(tempfile.gettempdir()) / "vascotv-ca-bundle.pem"
    conteudo = Path(certifi.where()).read_bytes() + b"\n" + INTERMEDIARIO.read_bytes()
    destino.write_bytes(conteudo)
    return str(destino)
