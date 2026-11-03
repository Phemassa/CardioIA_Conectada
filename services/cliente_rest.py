"""Cliente REST (Ir Alem 1): envia leituras simuladas e consulta o que a API registrou.

Com a API rodando (python -m services.api_rest):

    python -m services.cliente_rest
"""
import argparse
import random

import requests

TIMEOUT_S = 5


class ClienteCardioIA:
    def __init__(self, base_url: str = "http://127.0.0.1:5000", sessao=None):
        self.base_url = base_url.rstrip("/")
        self.sessao = sessao or requests.Session()

    def enviar_leitura(self, leitura: dict) -> dict:
        resposta = self.sessao.post(f"{self.base_url}/api/v1/leituras", json=leitura, timeout=TIMEOUT_S)
        resposta.raise_for_status()
        return resposta.json()

    def listar_leituras(self, dispositivo: str, limite: int = 20) -> list:
        return self._listar("leituras", dispositivo, limite)

    def listar_alertas(self, dispositivo: str, limite: int = 20) -> list:
        return self._listar("alertas", dispositivo, limite)

    def _listar(self, recurso: str, dispositivo: str, limite: int) -> list:
        resposta = self.sessao.get(f"{self.base_url}/api/v1/{recurso}",
                                   params={"dispositivo": dispositivo, "limite": limite},
                                   timeout=TIMEOUT_S)
        resposta.raise_for_status()
        return resposta.json()


def gerar_cenario(rng: random.Random, dispositivo: str) -> list:
    """Normal, taquicardia, febre e um paciente parado por 2 minutos de leituras."""
    def leitura(bpm, temp, mov):
        return {"dispositivo": dispositivo, "bpm": rng.randint(*bpm),
                "temp_c": round(rng.uniform(*temp), 1),
                "umid_pct": round(rng.uniform(50, 60), 1), "mov_mg": rng.randint(*mov)}

    return (
        [leitura((68, 84), (36.4, 36.9), (60, 400)) for _ in range(5)]
        + [leitura((130, 145), (36.6, 37.0), (60, 400)) for _ in range(3)]
        + [leitura((90, 100), (38.3, 38.8), (60, 400)) for _ in range(3)]
        + [leitura((60, 70), (36.3, 36.6), (0, 20)) for _ in range(24)]
    )


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--url", default="http://127.0.0.1:5000")
    args.add_argument("--dispositivo", default="wearable-01")
    args.add_argument("--semente", type=int, default=42)
    args = args.parse_args()

    cliente = ClienteCardioIA(args.url)
    rng = random.Random(args.semente)

    for leitura in gerar_cenario(rng, args.dispositivo):
        resposta = cliente.enviar_leitura(leitura)
        codigos = ",".join(r["codigo"] for r in resposta["riscos"]) or "-"
        email = f" | e-mail: {resposta['notificacao']}" if resposta["notificacao"] else ""
        print(f"bpm={leitura['bpm']:>3} temp={leitura['temp_c']:>4} mov={leitura['mov_mg']:>3} "
              f"-> {resposta['nivel']:<8} {codigos}{email}")

    print(f"\nRegistradas na API: {len(cliente.listar_leituras(args.dispositivo, 500))} leituras, "
          f"{len(cliente.listar_alertas(args.dispositivo, 500))} com alerta")


if __name__ == "__main__":
    main()
