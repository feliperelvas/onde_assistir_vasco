# Certificado intermediário

`sectigo-public-server-auth-ov-r36.pem` é o intermediário
**Sectigo Public Server Authentication CA OV R36** (válido até 21/03/2036), baixado de
`http://crt.sectigo.com/SectigoPublicServerAuthenticationCAOVR36.crt` — a URL que o próprio
certificado de `www.cbf.com.br` indica na extensão *Authority Information Access*.

Ele está aqui porque o servidor da CBF **não envia esse intermediário** no handshake TLS, o que
faz o OpenSSL (e portanto o runner Ubuntu do GitHub Actions) falhar com
`CERTIFICATE_VERIFY_FAILED`. O Windows não falha porque busca o certificado sozinho via AIA.

`src/vascotv/tls.py` concatena este arquivo ao bundle do `certifi`. É um certificado público de
CA, não um segredo, e a verificação do servidor continua completa.

Se um dia a CBF corrigir a cadeia, ou a Sectigo trocar o intermediário, este arquivo pode ser
removido ou substituído — `tls.py` volta ao `certifi` puro se ele não existir.
