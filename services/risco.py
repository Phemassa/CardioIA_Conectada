"""Regras de risco sobre as leituras de sinais vitais (Ir Alem 1).

Funcao pura, sem rede nem banco, para ser facil de testar e de auditar: num sistema de
saude, quem revisa precisa conseguir ler exatamente por que um alerta disparou.
Os limites sao os mesmos de firmware/sketch/config.h e do fluxo Node-RED.
"""
from dataclasses import dataclass
from typing import Optional, Sequence

BPM_ALTO = 120
BPM_BAIXO = 50
TEMP_FEBRE_C = 38.0
MOV_PARADO_MG = 50
# 24 leituras x 5 s = 2 min parado, mesmo valor de LIM_IMOBILIDADE_MS no firmware.
LEITURAS_PARA_IMOBILIDADE = 24

CRITICO = "critico"
ATENCAO = "atencao"
NORMAL = "normal"


@dataclass(frozen=True)
class Risco:
    codigo: str
    nivel: str
    explicacao: str


def avaliar(bpm: Optional[int], temp_c: Optional[float],
            mov_recentes_mg: Sequence[Optional[int]] = ()) -> list[Risco]:
    """Retorna os riscos encontrados. Campo ausente (None) nao gera alerta nem falso "normal".

    mov_recentes_mg: movimento das ultimas leituras, da mais antiga para a atual. Imobilidade
    so existe na serie: uma leitura parada isolada nao diz nada.
    """
    riscos = []
    if bpm is not None and bpm > BPM_ALTO:
        riscos.append(Risco("TAQUICARDIA", CRITICO, f"{bpm} bpm, acima do limite de {BPM_ALTO} bpm"))
    # bpm == 0 significa sensor sem sinal, nao coracao parado; ver a nota no firmware.
    if bpm is not None and 0 < bpm < BPM_BAIXO:
        riscos.append(Risco("BRADICARDIA", CRITICO, f"{bpm} bpm, abaixo do limite de {BPM_BAIXO} bpm"))
    if temp_c is not None and temp_c > TEMP_FEBRE_C:
        riscos.append(Risco("FEBRE", CRITICO, f"{temp_c:.1f} °C, acima do limite de {TEMP_FEBRE_C:.1f} °C"))

    janela = list(mov_recentes_mg)[-LEITURAS_PARA_IMOBILIDADE:]
    if len(janela) == LEITURAS_PARA_IMOBILIDADE and all(
        m is not None and m < MOV_PARADO_MG for m in janela
    ):
        riscos.append(Risco("IMOBILIDADE", ATENCAO,
                            f"sem movimento nas ultimas {LEITURAS_PARA_IMOBILIDADE} leituras"))
    return riscos


def nivel_geral(riscos: Sequence[Risco]) -> str:
    if any(r.nivel == CRITICO for r in riscos):
        return CRITICO
    return ATENCAO if riscos else NORMAL
