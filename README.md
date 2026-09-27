# Onde assistir o Vasco

Monitor do calendário da CBF que avisa no Telegram **onde assistir os jogos do time
profissional do Vasco** no Campeonato Brasileiro e na Copa do Brasil. Roda de graça no
GitHub Actions.

Duas mensagens, e só elas:

- **Mudanças** — rodada nova publicada, jogo remarcado, troca de transmissão ou de estádio.
- **Lembrete** — na manhã do dia do jogo, com horário, estádio e onde passa.

Nos outros momentos fica calado.

## Como ele obtém os dados

A página [onde-assistir](https://www.cbf.com.br/futebol-brasileiro/onde-assistir) é Next.js e
entrega a tabela **vazia**: o HTML só tem o *skeleton* de carregamento. Não há o que raspar.
Os dados vêm de um proxy JSON do próprio site, público e sem autenticação:

```
GET https://www.cbf.com.br/api/cbf/onde-assistir/jogos
    ?dataInicio=2026-09-27&dataTermino=2027-11-01&campeonato=42&page=1&pageSize=2000
```

O site pagina de 15 em 15, mas o backend aceita `pageSize` maior — a temporada inteira
(~1200 jogos) cabe em uma requisição de pouco mais de um segundo. São 2 requisições por
execução de `sync` — 4 por dia, somando os dois horários.

### Profissional vs. base: a regra que parece simples e não é

Filtrar pelo time **não** separa o profissional das categorias de base. Série A, Sub-20, SUB17 e
Copa do Brasil Feminino aparecem todos com o mesmo `id=60646` ("Vasco da Gama Saf"). A separação
tem de ser pela **categoria**:

| Campeonato | Profissional | Descartado |
|---|---|---|
| `42` Brasileiro | Série A=`1`, B=`2`, C=`3`, D=`5` | Sub-20=`56`, SUB17=`62` |
| `24` Copa do Brasil | Profissional=`4` | Feminino=`55`, Sub-20=`56`, Sub-15=`97` |

É uma *allowlist* (`1,2,3,4,5`), não uma *blocklist*: assim o monitor continua correto se o Vasco
cair para a Série B. Categoria fora das duas listas é **incluída e sinalizada** na mensagem —
avisar demais é melhor que perder um jogo em silêncio.

### O certificado da CBF

`www.cbf.com.br` tem a cadeia TLS mal configurada: não envia o intermediário
`Sectigo Public Server Authentication CA OV R36` que emitiu seu certificado. O Windows disfarça
o problema (busca o certificado faltante pela extensão AIA), mas OpenSSL não — e no runner Ubuntu
a conexão falharia com `CERTIFICATE_VERIFY_FAILED`. Por isso o intermediário está versionado em
[`certs/`](certs/) e é concatenado ao bundle do `certifi` em tempo de execução
([`src/vascotv/tls.py`](src/vascotv/tls.py)). A verificação segue completa — em nenhum momento se
usa `verify=False`.

## Rodando localmente

```bash
pip install -r requirements-dev.txt
export PYTHONPATH=src            # no PowerShell: $env:PYTHONPATH = "src"

python -m vascotv sync --dry-run       # busca de verdade, imprime, não envia nem grava
python -m vascotv lembrete --dry-run   # mostra o lembrete de hoje
pytest                                  # 58 testes, nenhum toca a rede
```

`--dry-run` nunca envia mensagem nem escreve em `data/` — é seguro rodar antes de configurar
qualquer secret.

## Configurando o Telegram

1. No Telegram, fale com **[@BotFather](https://t.me/BotFather)** e mande `/newbot`. Escolha nome
   e username; ele devolve um token no formato `123456789:AAE...`.
2. **Mande qualquer mensagem para o seu bot** (ele não pode escrever para você antes disso).
3. Abra no navegador, trocando `<TOKEN>` pelo seu:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   e copie o número em `"chat":{"id":...}` — é o seu `chat_id`.
4. No repositório do GitHub: **Settings → Secrets and variables → Actions → New repository secret**:

   | Secret | Valor |
   |---|---|
   | `TELEGRAM_BOT_TOKEN` | o token do passo 1 |
   | `TELEGRAM_CHAT_ID` | o id do passo 3 |

Para testar sem o GitHub, exporte as duas variáveis no shell e rode sem `--dry-run`.

## Como roda no GitHub Actions

[`.github/workflows/vasco.yml`](.github/workflows/vasco.yml) — um único workflow, porque os dois
comandos escrevem em `data/` e pushes concorrentes dariam conflito.

| Cron (UTC) | Brasília | Comando |
|---|---|---|
| `0 11 * * *` | 08:00 | `sync` |
| `0 23 * * *` | 20:00 | `sync` |
| `0 12 * * *` | 09:00 | `lembrete` |

Dá para disparar à mão em **Actions → Onde assistir o Vasco → Run workflow**, escolhendo o comando
e deixando `dry_run` marcado para só ver o log.

Dois detalhes do cron do GitHub que explicam comportamentos estranhos:

- **Ele atrasa.** De 5 a 30 minutos em horário de pico. O lembrete das 09:00 pode chegar 09:20.
- **Ele é desativado após 60 dias sem atividade no repositório.** O commit do snapshot em cada
  execução serve de mitigação; se ainda assim adormecer, troque o `GITHUB_TOKEN` por um PAT.

## Estado versionado

- **`data/jogos.json`** — o calendário como estava na última execução. É a base de comparação, e
  o `git log` dele vira o histórico de remarcações. Gravado de forma determinística (chaves
  ordenadas, sem timestamp) para que o workflow commite **somente** quando algo mudou de verdade.
- **`data/lembretes.json`** — IDs já lembrados, para o cron não avisar duas vezes do mesmo jogo.
  É podado a cada execução para não crescer sem fim.

O placar não é guardado nem comparado: é o único campo volátil da API, e incluí-lo faria o bot
disparar a cada gol e sujar o histórico de commits.

Na **primeira execução** não há snapshot: o monitor grava a linha de base e não notifica nada, em
vez de despejar o calendário inteiro no chat.

## Estrutura

```
src/vascotv/
  config.py    IDs, categorias, janela, fuso — tudo que muda de temporada
  cbf.py       cliente da API (retry, paginação)
  tls.py       o bundle de certificados que contorna a cadeia da CBF
  models.py    o jogo normalizado
  filtros.py   Vasco? profissional?
  diff.py      snapshot anterior × novo → eventos
  render.py    eventos → mensagem HTML
  telegram.py  envio
  cli.py       `sync` e `lembrete`
```

## Custo, e por que GitHub Actions

Grátis e ilimitado em repositório público (2.000 min/mês no privado); cada execução leva ~20 s,
o que dá algo em torno de 30 min/mês. A vantagem sobre as alternativas é que **o git já serve de
banco de dados** para o snapshot e de histórico — Cloudflare Workers Cron exigiria Workers KV,
e Val Town ou Deno Deploy Cron precisariam de armazenamento externo.

## Acompanhar outros campeonatos

`CAMPEONATOS` em [`config.py`](src/vascotv/config.py) aceita qualquer um dos que a API expõe:
`1026` Supercopa do Brasil, `1016` Brasileiro Feminino, `1001` Copa do Nordeste, `1008` Copa
Verde, `1032` Liga de Desenvolvimento, `1067` Copa Sul-Sudeste. Estaduais não entram — a CBF não
os publica nesse endpoint.
