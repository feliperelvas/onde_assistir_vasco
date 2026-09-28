# Onde assistir o Vasco

Bot de Telegram que acompanha o calendário da CBF e avisa **onde assistir os jogos do time
profissional do Vasco** no Campeonato Brasileiro e na Copa do Brasil. Roda sozinho e de graça no
GitHub Actions: nenhum servidor, nenhum banco de dados.

## O que o bot faz

Ele manda duas mensagens, e só elas. No resto do tempo fica calado.

**Mudanças no calendário** — quando a CBF publica uma rodada nova, remarca um jogo, troca a
transmissão ou o estádio, ou tira um jogo do calendário. Vários eventos da mesma execução vão
juntos em uma mensagem:

```
🔔 Calendário do Vasco atualizado

🔔 Botafogo x Vasco
🏆 Brasileirão · Série A — rodada 29
• horário: 20:30 → 21:30
• transmissão: Amazon Prime → Amazon Prime, Globo
🕐 07/10 (qua) 21:30
```

**Lembrete** — na manhã do dia do jogo:

```
📅 Hoje tem Vasco!

⚽ Botafogo x Vasco
🏆 Brasileirão · Série A — rodada 29
🕐 20:30 (horário de Brasília)
🏟 Nilton Santos — Rio de Janeiro, RJ
📺 Amazon Prime
```

Há ainda um terceiro comando, `testar`, que só existe para conferir que o token e o chat estão
certos: manda uma mensagem fixa, sem consultar a CBF nem gravar nada.

Regras que definem o comportamento:

- **Só o profissional masculino.** Sub-20, Sub-17, Sub-15 e feminino ficam de fora (ver abaixo
  por que isso não é trivial).
- **Só jogos futuros geram aviso.** Jogo que já aconteceu e sai da janela de consulta não é
  anunciado como "removido", e correções em jogos disputados não viram ruído.
- **O placar é ignorado.** É o único campo que muda durante o jogo; considerá-lo faria o bot
  disparar a cada gol.
- **Um lembrete por jogo.** Se o cron rodar duas vezes no mesmo dia, o segundo não repete.
- **Na dúvida, avisa.** Categoria que o bot não conhece é incluída com um alerta, em vez de
  descartada em silêncio.

## Quando roda

[`.github/workflows/vasco.yml`](.github/workflows/vasco.yml):

| Cron (UTC) | Brasília | Comando |
|---|---|---|
| `0 11 * * *` | 08:00 | `sync` — busca o calendário e avisa mudanças |
| `0 23 * * *` | 20:00 | `sync` |
| `0 12 * * *` | 09:00 | `lembrete` — avisa se hoje tem jogo |

É um único workflow, que nunca roda duas vezes ao mesmo tempo, porque os comandos escrevem em
`data/` e pushes concorrentes dariam conflito.

Para disparar à mão: **Actions → Onde assistir o Vasco → Run workflow**, escolhendo `sync`,
`lembrete` ou `testar`. A caixa `dry_run` vem **marcada**: assim ele só mostra no log o que faria.
Desmarque para enviar de verdade.

Dois detalhes do cron do GitHub que explicam comportamentos estranhos:

- **Ele atrasa.** De 5 a 30 minutos em horário de pico. O lembrete das 09:00 pode chegar 09:20.
- **Ele desliga após 60 dias sem atividade no repositório.** O workflow só commita quando o
  calendário muda, o que durante a temporada acontece com frequência, mas pode não acontecer no
  recesso. O GitHub avisa por e-mail antes; para religar, basta **Actions → Onde assistir o
  Vasco → Enable workflow**.

## Instalação

1. **Crie o bot.** No Telegram, fale com **[@BotFather](https://t.me/BotFather)** e mande
   `/newbot`. Ele devolve um token no formato `123456789:AAE...`.
2. **Mande qualquer mensagem para o seu bot** (ele não pode escrever para você antes disso).
3. **Descubra o `chat_id`.** Abra no navegador, trocando `<TOKEN>` pelo seu,
   `https://api.telegram.org/bot<TOKEN>/getUpdates` e copie o número em `"chat":{"id":...}`.
4. **Cadastre os secrets** em **Settings → Secrets and variables → Actions → Repository
   secrets → New repository secret**:

   | Secret | Valor |
   |---|---|
   | `TELEGRAM_BOT_TOKEN` | o token do passo 1 |
   | `TELEGRAM_CHAT_ID` | o id do passo 3 |

   Têm de ser **Repository secrets**, não *Environment secrets*: o job não declara
   `environment:`, então secrets de ambiente chegariam vazios.
5. **Teste o envio**: Run workflow com `testar` e `dry_run` desmarcado. Deve chegar
   `✅ Teste do monitor do Vasco (...). O envio está funcionando.`
6. **Opcional**: rode `sync` com `dry_run` marcado para ver no log os jogos que ele encontrou.

Se você for fazer push de alterações no workflow pelo `gh`, o token dele precisa do escopo
`workflow` (o `repo` sozinho não basta — o GitHub recusa com *refusing to allow an OAuth App to
create or update workflow*). Para conceder, num terminal interativo:
`gh auth refresh -h github.com -s workflow`.

## Rodando localmente

```bash
pip install -r requirements-dev.txt
export PYTHONPATH=src            # no PowerShell: $env:PYTHONPATH = "src"

python -m vascotv sync --dry-run       # busca de verdade, imprime, não envia nem grava
python -m vascotv lembrete --dry-run   # mostra o lembrete de hoje, se houver jogo
python -m vascotv testar --dry-run     # mostra a mensagem de teste
pytest                                  # 60 testes, nenhum toca a rede
```

`--dry-run` nunca envia mensagem nem escreve em `data/`, então é seguro rodar sem configurar
nada. Para enviar de verdade a partir da sua máquina, exporte `TELEGRAM_BOT_TOKEN` e
`TELEGRAM_CHAT_ID` no shell e rode sem `--dry-run`.

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
execução de `sync` (uma por campeonato), 4 por dia.

A janela vai de 7 dias atrás a 400 dias à frente, para pegar a temporada seguinte assim que a CBF
publicar o calendário.

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

## Estado versionado

O git faz as vezes de banco de dados:

- **`data/jogos.json`** — o calendário como estava na última execução. É a base de comparação, e
  o `git log` dele vira o histórico de remarcações. Gravado de forma determinística (chaves
  ordenadas, sem timestamp) para que o workflow commite **somente** quando algo mudou de verdade.
- **`data/lembretes.json`** — IDs de jogos já lembrados, para não avisar duas vezes. É podado a
  cada execução para não crescer sem fim. Só aparece depois do primeiro lembrete.

Na **primeira execução**, sem snapshot, o monitor grava a linha de base e não notifica nada, em
vez de despejar o calendário inteiro no chat.

Os commits automáticos são feitos pelo `github-actions[bot]` com `[skip ci]` na mensagem.

## O que é público e o que não é

O repositório é público — o que dá Actions ilimitado — e foi montado para que isso não exponha
nada:

- **Token do bot e `chat_id` só existem nos secrets do GitHub.** Não estão em nenhum arquivo nem
  no histórico; no log do Actions aparecem mascarados como `***`.
- **O token nunca vai para o log.** Ele faz parte da URL da API do Telegram, então em caso de
  erro o bot registra só o código HTTP e a descrição devolvida, nunca a URL
  ([`telegram.py`](src/vascotv/telegram.py)).
- **`data/` contém só dados públicos da CBF** (jogos, estádios, transmissões) e IDs de jogo.
- **O `.pem` em `certs/` é um certificado público de CA**, não uma chave privada.
- `.env` está no `.gitignore`, caso você guarde as variáveis num arquivo para rodar localmente.

Quem fizer fork recebe o código, mas não os secrets: precisa criar o próprio bot.

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
  storage.py   leitura e escrita de data/
  cli.py       `sync`, `lembrete` e `testar`
tests/         60 testes com respostas reais da API gravadas em fixtures/
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
