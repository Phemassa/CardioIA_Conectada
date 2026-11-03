"""Publica no broker o mesmo JSON do firmware, para testar o dashboard sem abrir o Wokwi.

Nao substitui o ESP32: o buffer aqui e uma lista Python. Serve para exercitar o fluxo
Node-RED de forma repetivel, com todos os cenarios em poucos minutos.

    python scripts/simula_esp32.py                # roteiro completo, ~2 min
    python scripts/simula_esp32.py --intervalo 1  # mais rapido
"""
import argparse
import json
import random
import time
from dataclasses import dataclass

import paho.mqtt.client as mqtt

TOPICO_BASE = "cardioia/grupo-zion/wearable-01"


@dataclass
class Cenario:
    nome: str
    amostras: int
    bpm: tuple
    temp: tuple
    mov: tuple = (60, 400)
    online: bool = True


ROTEIRO = [
    Cenario("Normal", 8, (68, 84), (36.4, 36.9)),
    Cenario("Taquicardia", 6, (128, 145), (36.6, 37.0)),
    Cenario("Febre", 6, (88, 104), (38.2, 38.8)),
    Cenario("Offline com taquicardia no buffer", 8, (125, 140), (36.8, 37.2), online=False),
    Cenario("Normal apos reconexao", 8, (70, 82), (36.5, 36.8)),
    Cenario("Imobilidade", 4, (60, 70), (36.3, 36.6), mov=(0, 10)),
]


def alertas_do_edge(bpm: int, temp: float, mov: int) -> list:
    """Mesmos limites de firmware/sketch/config.h."""
    alertas = []
    if bpm > 120:
        alertas.append("TAQUICARDIA")
    if 0 < bpm < 50:
        alertas.append("BRADICARDIA")
    if temp > 38.0:
        alertas.append("FEBRE")
    if mov < 50:
        alertas.append("IMOBILIDADE")
    return alertas


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--broker", default="broker.hivemq.com")
    args.add_argument("--porta", type=int, default=1883)
    args.add_argument("--intervalo", type=float, default=2.0, help="segundos entre amostras")
    args.add_argument("--semente", type=int, default=42)
    args = args.parse_args()

    rng = random.Random(args.semente)
    cliente = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"cardioia-simulador-{rng.randrange(16**8):08x}",
    )
    cliente.will_set(f"{TOPICO_BASE}/status", "offline", qos=1, retain=True)
    cliente.connect(args.broker, args.porta, keepalive=30)
    cliente.loop_start()
    cliente.publish(f"{TOPICO_BASE}/status", "online", qos=1, retain=True)

    seq = 0
    fila: list = []  # (instante de captura, amostra)

    def publicar(amostra: dict, capturada_em: float, restantes: int) -> None:
        idade = int(time.time() - capturada_em)
        corpo = {**amostra, "age_s": idade, "replay": idade >= 10, "fila": restantes}
        cliente.publish(f"{TOPICO_BASE}/telemetria", json.dumps(corpo), qos=0).wait_for_publish(5)

    for cenario in ROTEIRO:
        print(f"== {cenario.nome}", flush=True)
        if not cenario.online:
            cliente.publish(f"{TOPICO_BASE}/status", "offline", qos=1, retain=True)

        for _ in range(cenario.amostras):
            bpm = rng.randint(*cenario.bpm)
            temp = round(rng.uniform(*cenario.temp), 1)
            mov = rng.randint(*cenario.mov)
            fila.append((time.time(), {
                "dev": "wearable-01", "seq": seq, "temp_c": temp,
                "umid_pct": round(rng.uniform(50, 60), 1), "bpm": bpm, "mov_mg": mov,
                "alertas": alertas_do_edge(bpm, temp, mov),
            }))
            seq += 1

            if cenario.online:
                while fila:  # A fila esvazia da mais antiga para a mais nova, como no firmware
                    capturada_em, amostra = fila.pop(0)
                    publicar(amostra, capturada_em, len(fila))
            time.sleep(args.intervalo)

        if not cenario.online:
            print(f"   {len(fila)} amostras retidas no buffer", flush=True)
            cliente.publish(f"{TOPICO_BASE}/status", "online", qos=1, retain=True)

    print(f"Fim: {seq} amostras publicadas", flush=True)
    # Desconexao limpa nao dispara o Last Will: avisa o status antes de sair, como o firmware.
    cliente.publish(f"{TOPICO_BASE}/status", "offline", qos=1, retain=True).wait_for_publish(5)
    cliente.loop_stop()
    cliente.disconnect()


if __name__ == "__main__":
    main()
