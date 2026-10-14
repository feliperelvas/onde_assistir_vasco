# Onde assistir o Vasco

Bot de Telegram que avisa **onde assistir os jogos do time profissional do Vasco** no Campeonato
Brasileiro, na Copa do Brasil e na Copa Sul-Americana. Roda sozinho e de graça no GitHub Actions:
sem servidor e sem banco de dados.

## O que o bot faz

**Avisa mudanças no calendário** — rodada nova, jogo remarcado, troca de transmissão ou de
estádio:

```
🔔 Calendário do Vasco atualizado

🔔 Botafogo x Vasco
🏆 Brasileirão · Série A — rodada 29
• horário: 20:30 → 21:30
• transmissão: Amazon Prime → Amazon Prime, Globo
🕐 07/10 (qua) 21:30
```

**Lembra no dia do jogo**, pela manhã:

```
📅 Hoje tem Vasco!

⚽ Botafogo x Vasco
🏆 Brasileirão · Série A — rodada 29
🕐 20:30 (horário de Brasília)
🏟 Nilton Santos — Rio de Janeiro, RJ
📺 Amazon Prime
```

No resto do tempo, fica calado. Só entram jogos do time profissional masculino.

## Como usar o seu

1. **Faça um fork** deste repositório.
2. **Crie o bot.** No Telegram, fale com [@BotFather](https://t.me/BotFather) e mande `/newbot`.
   Ele devolve um token no formato `123456789:AAE...`.
3. **Mande qualquer mensagem para o seu bot** (ele não pode escrever para você antes disso).
4. **Descubra o `chat_id`.** Abra `https://api.telegram.org/bot<TOKEN>/getUpdates` no navegador,
   trocando `<TOKEN>` pelo seu, e copie o número em `"chat":{"id":...}`.
5. **Cadastre os secrets** em **Settings → Secrets and variables → Actions → New repository
   secret**:

   | Secret | Valor |
   |---|---|
   | `TELEGRAM_BOT_TOKEN` | o token do passo 2 |
   | `TELEGRAM_CHAT_ID` | o id do passo 4 |

6. **Teste**: em **Actions → Onde assistir o Vasco → Run workflow**, escolha `testar` e desmarque
   `dry_run`. Deve chegar uma mensagem de confirmação no Telegram.

A partir daí o bot roda sozinho duas vezes por dia, mais o lembrete de manhã.

## Rodando localmente

```bash
pip install -r requirements-dev.txt
export PYTHONPATH=src            # no PowerShell: $env:PYTHONPATH = "src"

python -m vascotv sync --dry-run       # busca o calendário e mostra as mudanças
python -m vascotv lembrete --dry-run   # mostra o lembrete de hoje, se houver jogo
pytest
```

Com `--dry-run` nada é enviado nem gravado. Para enviar de verdade, exporte `TELEGRAM_BOT_TOKEN`
e `TELEGRAM_CHAT_ID` e rode sem a flag.

## Privacidade

O token do bot e o `chat_id` ficam só nos secrets do GitHub: não estão em nenhum arquivo nem no
histórico, e o bot nunca os escreve no log. A pasta `data/` guarda apenas o calendário público
dos jogos.
