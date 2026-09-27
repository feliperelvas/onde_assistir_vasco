"""Modelo de um jogo, normalizado a partir da resposta da API da CBF."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from . import config

# Abreviações fixas em vez de locale: o runner do GitHub Actions não tem
# pt_BR instalado e `locale.setlocale` falharia lá.
DIAS_SEMANA = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")


@dataclass(frozen=True)
class Time:
    id: str
    nome: str
    url_escudo: str = ""

    @classmethod
    def from_api(cls, bruto: dict) -> "Time":
        return cls(
            id=str(bruto.get("id") or ""),
            nome=(bruto.get("nome") or "").strip(),
            url_escudo=bruto.get("url_escudo") or "",
        )

    def to_dict(self) -> dict:
        return {"id": self.id, "nome": self.nome, "url_escudo": self.url_escudo}


@dataclass(frozen=True)
class Jogo:
    """Um jogo do calendário da CBF.

    O placar (`gols`) de propósito não é modelado nem persistido: é o único campo
    volátil da API e guardá-lo faria o snapshot mudar a cada gol, sujando o
    histórico de commits sem que nada do calendário tenha mudado.
    """

    id_jogo: str
    data: str  # dd/mm/yyyy, horário de Brasília
    hora: str  # HH:MM, horário de Brasília
    local: str
    rodada: str
    grupo: str
    num_jogo: str
    mandante: Time
    visitante: Time
    transmissoes: tuple[str, ...]
    campeonato_id: str
    campeonato_nome: str
    categoria_id: str
    categoria_nome: str

    # --- construção ---------------------------------------------------------
    @classmethod
    def from_api(cls, bruto: dict) -> "Jogo":
        competicao = bruto.get("competicao") or {}
        transmissoes = tuple(
            sorted(
                (t.get("nome") or "").strip()
                for t in (bruto.get("transmissoes") or [])
                if (t.get("nome") or "").strip()
            )
        )
        return cls(
            id_jogo=str(bruto.get("id_jogo") or ""),
            data=(bruto.get("data") or "").strip(),
            hora=(bruto.get("hora") or "").strip(),
            local=(bruto.get("local") or "").strip(),
            rodada=str(bruto.get("rodada") or "").strip(),
            grupo=(bruto.get("grupo") or "").strip(),
            num_jogo=str(bruto.get("num_jogo") or "").strip(),
            mandante=Time.from_api(bruto.get("mandante") or {}),
            visitante=Time.from_api(bruto.get("visitante") or {}),
            transmissoes=transmissoes,
            campeonato_id=str(competicao.get("campeonato_id") or ""),
            campeonato_nome=(competicao.get("campeonato_nome") or "").strip(),
            categoria_id=str(competicao.get("categoria_id") or ""),
            categoria_nome=(competicao.get("categoria_nome") or "").strip(),
        )

    def to_dict(self) -> dict:
        return {
            "id_jogo": self.id_jogo,
            "data": self.data,
            "hora": self.hora,
            "local": self.local,
            "rodada": self.rodada,
            "grupo": self.grupo,
            "num_jogo": self.num_jogo,
            "mandante": self.mandante.to_dict(),
            "visitante": self.visitante.to_dict(),
            "transmissoes": list(self.transmissoes),
            "campeonato_id": self.campeonato_id,
            "campeonato_nome": self.campeonato_nome,
            "categoria_id": self.categoria_id,
            "categoria_nome": self.categoria_nome,
        }

    @classmethod
    def from_dict(cls, bruto: dict) -> "Jogo":
        return cls(
            id_jogo=bruto["id_jogo"],
            data=bruto["data"],
            hora=bruto["hora"],
            local=bruto["local"],
            rodada=bruto["rodada"],
            grupo=bruto.get("grupo", ""),
            num_jogo=bruto.get("num_jogo", ""),
            mandante=Time(**bruto["mandante"]),
            visitante=Time(**bruto["visitante"]),
            # Reordenar na leitura garante que o diff não veja diferença onde
            # só a ordem da API mudou.
            transmissoes=tuple(sorted(bruto.get("transmissoes") or [])),
            campeonato_id=bruto["campeonato_id"],
            campeonato_nome=bruto["campeonato_nome"],
            categoria_id=bruto["categoria_id"],
            categoria_nome=bruto["categoria_nome"],
        )

    # --- derivados ----------------------------------------------------------
    @property
    def chave(self) -> str:
        return self.id_jogo

    @property
    def inicio(self) -> datetime | None:
        """Início do jogo no fuso de Brasília, ou None se a API mandar algo torto."""
        try:
            ingenuo = datetime.strptime(f"{self.data} {self.hora}", "%d/%m/%Y %H:%M")
        except ValueError:
            return None
        return ingenuo.replace(tzinfo=config.FUSO)

    @property
    def em_casa(self) -> bool:
        return self.mandante.id == config.VASCO_ID

    @property
    def adversario(self) -> str:
        outro = self.visitante if self.em_casa else self.mandante
        return exibir_time(outro.nome)

    @property
    def confronto(self) -> str:
        return f"{exibir_time(self.mandante.nome)} x {exibir_time(self.visitante.nome)}"

    @property
    def competicao(self) -> str:
        campeonato = config.CAMPEONATOS.get(self.campeonato_id, self.campeonato_nome)
        if self.categoria_nome:
            return f"{campeonato} · {self.categoria_nome}"
        return campeonato

    @property
    def data_hora_curta(self) -> str:
        """Ex.: '07/10 (qua) 20:30'."""
        inicio = self.inicio
        if inicio is None:
            return f"{self.data} {self.hora}".strip()
        dia = DIAS_SEMANA[inicio.weekday()]
        return f"{inicio:%d/%m} ({dia}) {inicio:%H:%M}"

    @property
    def local_formatado(self) -> str:
        return formatar_local(self.local)

    @property
    def onde_assistir(self) -> str:
        return ", ".join(self.transmissoes) if self.transmissoes else "Não informado"


def formatar_local(local: str) -> str:
    """'Nilton Santos - Rio de Janeiro - RJ' -> 'Nilton Santos — Rio de Janeiro, RJ'."""
    partes = [parte.strip() for parte in local.split(" - ") if parte.strip()]
    if len(partes) >= 3:
        return f"{partes[0]} — {', '.join(partes[1:])}"
    if len(partes) == 2:
        return f"{partes[0]} — {partes[1]}"
    return local


def exibir_time(nome: str) -> str:
    """'Vasco da Gama Saf' é o nome jurídico na API; na mensagem fica feio."""
    if "vasco" in nome.lower():
        return config.VASCO_APELIDO
    return nome
