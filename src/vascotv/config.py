"""Configuração central do monitor.

Tudo que pode mudar de temporada para temporada mora aqui: IDs de campeonato,
categorias consideradas profissionais, janela de consulta e caminhos de estado.
"""

from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]

# --- Time -------------------------------------------------------------------
# Na API o Vasco aparece como "Vasco da Gama Saf" sob um único ID, usado tanto
# pelo profissional quanto pelas categorias de base e pelo feminino. Por isso o
# ID sozinho NÃO separa o time profissional; ver CATEGORIAS_PROFISSIONAIS.
VASCO_ID = "60646"
VASCO_APELIDO = "Vasco"

# --- Competições ------------------------------------------------------------
CAMPEONATOS = {
    "42": "Brasileirão",
    "24": "Copa do Brasil",
}

# Outros campeonatos que a API expõe, caso um dia queira acompanhar:
#   1026 Supercopa do Brasil   1016 Brasileiro Feminino   1001 Copa do Nordeste
#   1008 Copa Verde            1032 Liga de Desenvolvimento
#   1067 Copa Sul-Sudeste

# Jogos do FotMob não têm categoria; as ligas acompanhadas lá são só de
# profissionais, então todo jogo de lá recebe esta (ver vascotv.fotmob).
CATEGORIA_FOTMOB = "fotmob"

# Allowlist em vez de blocklist: continua correto se o Vasco cair para a Série B.
#   1 Série A · 2 Série B · 3 Série C · 5 Série D · 4 Profissional (Copa do Brasil)
CATEGORIAS_PROFISSIONAIS = {"1", "2", "3", "4", "5", CATEGORIA_FOTMOB}

# Categorias que sabidamente NÃO são o time profissional masculino.
#   55 Feminino · 56 Sub-20 · 62 SUB17 · 97 Sub-15
CATEGORIAS_BASE = {"55", "56", "62", "97"}

# --- FotMob -----------------------------------------------------------------
# A Sul-Americana não está na CBF, e o site da CONMEBOL barra o runner do GitHub
# (firewall anti-robô) e escolhe as emissoras pelo país de quem acessa. O FotMob
# não é oficial, mas tem um guia de TV por país com o país na URL. Os termos do
# site não permitem uso automatizado: se ele bloquear, o bot avisa no Telegram e
# segue com a CBF (ver vascotv.fotmob e cli.comando_sync).
FOTMOB_URL = "https://www.fotmob.com"
FOTMOB_VASCO_ID = "10276"
FOTMOB_PAIS = "br"

# leagueId do FotMob -> nome na mensagem. O ID é da competição, não da edição,
# então não muda de um ano para o outro (é o número em fotmob.com/leagues/<ID>/...).
FOTMOB_LIGAS = {
    "299": "Copa Sul-Americana",
}

# Fases como vêm do FotMob -> como aparecem na mensagem.
FOTMOB_FASES = {
    "Group Stage": "Fase de grupos",
    "1st Round": "Primeira fase",
    "Knockout Round Play-offs": "Playoffs das oitavas",
    "Round of 16": "Oitavas de final",
    "8th Finals": "Oitavas de final",
    "Quarter-finals": "Quartas de final",
    "Semi-finals": "Semifinal",
    "Final": "Final",
}

# O guia usa isto no lugar do nome quando ainda não há canal.
FOTMOB_SEM_CANAL = {"Canal a confirmar"}

# --- API --------------------------------------------------------------------
API_URL = "https://www.cbf.com.br/api/cbf/onde-assistir/jogos"
# Identificar o cliente e boa pratica; troque pela URL do seu repositorio se
# quiser deixar um contato para a CBF.
USER_AGENT = "onde-assistir-vasco/1.0 (monitor pessoal de transmissoes)"

# O site pagina de 15 em 15, mas o backend aceita pageSize maior: a temporada
# inteira (~1200 jogos) vem em uma requisição. Ainda assim paginamos de verdade
# pelo meta.last_page, para não depender desse limite.
PAGE_SIZE = 2000
TIMEOUT = 30
TENTATIVAS = 3
# HTTP 429 (limite de requisições) é retentado com espera maior; ver vascotv.espera.
ESPERA_429 = 10
ESPERA_MAXIMA = 60

# --- Janela de consulta -----------------------------------------------------
# O passado curto mantém no snapshot o jogo que acabou de acontecer; os 400 dias
# à frente capturam a temporada seguinte assim que a CBF publicar o calendário.
DIAS_PASSADO = 7
DIAS_FUTURO = 400

# --- Fuso -------------------------------------------------------------------
# A API devolve data/hora no horário de Brasília, sem indicação de fuso.
FUSO = ZoneInfo("America/Sao_Paulo")

# --- Estado -----------------------------------------------------------------
SNAPSHOT_PATH = ROOT / "data" / "jogos.json"
LEMBRETES_PATH = ROOT / "data" / "lembretes.json"
ALERTAS_PATH = ROOT / "data" / "alertas.json"
