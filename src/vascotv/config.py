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

# Allowlist em vez de blocklist: continua correto se o Vasco cair para a Série B.
#   1 Série A · 2 Série B · 3 Série C · 5 Série D · 4 Profissional (Copa do Brasil)
CATEGORIAS_PROFISSIONAIS = {"1", "2", "3", "4", "5"}

# Categorias que sabidamente NÃO são o time profissional masculino.
#   55 Feminino · 56 Sub-20 · 62 SUB17 · 97 Sub-15
CATEGORIAS_BASE = {"55", "56", "62", "97"}

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
