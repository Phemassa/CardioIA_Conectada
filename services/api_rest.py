"""API REST de sinais vitais (Ir Alem 1): recebe leituras, avalia risco e dispara alertas.

    python -m services.api_rest      # http://127.0.0.1:5000

    POST /api/v1/leituras            registra uma leitura e devolve os riscos encontrados
    GET  /api/v1/leituras?dispositivo=wearable-01&limite=20
    GET  /api/v1/alertas?dispositivo=wearable-01&limite=20
    GET  /api/v1/saude

Guarda tudo em memoria: basta para a demonstracao e nao deixa dado para tras.
"""
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import Lock

from flask import Flask, jsonify, request

from services import risco
from services.email_alerta import NotificadorEmail

log = logging.getLogger(__name__)

MAX_LEITURAS_POR_DISPOSITIVO = 5000  # Mesmo limite pensado para o historico: nao cresce sem fim

# campo -> (minimo, maximo). Fora da faixa e erro de sensor ou de envio, nao sinal clinico.
FAIXAS = {
    "bpm": (0, 255),
    "temp_c": (-40, 80),  # Faixa de medicao do DHT22
    "umid_pct": (0, 100),
    "mov_mg": (0, 65535),
}


def validar(corpo) -> tuple[dict, list[str]]:
    if not isinstance(corpo, dict):
        return {}, ["o corpo precisa ser um objeto JSON"]
    erros = []
    dispositivo = corpo.get("dispositivo")
    if not isinstance(dispositivo, str) or not dispositivo.strip():
        erros.append("dispositivo e obrigatorio")

    leitura = {"dispositivo": dispositivo}
    for campo, (minimo, maximo) in FAIXAS.items():
        valor = corpo.get(campo)
        if valor is None:  # Sensor sem leitura e permitido; o campo fica como null
            leitura[campo] = None
        # bool e subclasse de int em Python: true nao pode valer como 1 bpm.
        elif isinstance(valor, bool) or not isinstance(valor, (int, float)):
            erros.append(f"{campo} precisa ser numerico")
        elif not minimo <= valor <= maximo:
            erros.append(f"{campo} fora da faixa {minimo}..{maximo}")
        else:
            leitura[campo] = valor
    return leitura, erros


def criar_app(notificador: NotificadorEmail | None = None) -> Flask:
    app = Flask(__name__)
    notificador = notificador or NotificadorEmail()
    leituras = defaultdict(lambda: deque(maxlen=MAX_LEITURAS_POR_DISPOSITIVO))
    alertas = defaultdict(lambda: deque(maxlen=MAX_LEITURAS_POR_DISPOSITIVO))
    trava = Lock()

    def limite_da_consulta() -> int:
        try:
            return max(1, min(int(request.args.get("limite", 20)), 500))
        except ValueError:
            return 20

    @app.post("/api/v1/leituras")
    def registrar_leitura():
        leitura, erros = validar(request.get_json(silent=True))
        if erros:
            return jsonify(erros=erros), 400

        leitura["recebida_em"] = datetime.now(timezone.utc).isoformat()
        dispositivo = leitura["dispositivo"]
        with trava:
            historico = leituras[dispositivo]
            historico.append(leitura)
            movimento = [l["mov_mg"] for l in list(historico)[-risco.LEITURAS_PARA_IMOBILIDADE:]]
            riscos = risco.avaliar(leitura["bpm"], leitura["temp_c"], movimento)
            nivel = risco.nivel_geral(riscos)
            if riscos:
                alertas[dispositivo].append({
                    **leitura, "nivel": nivel, "riscos": [r.codigo for r in riscos],
                })

        # A leitura ja esta salva: falha de e-mail nao pode devolver erro nem perder o dado.
        notificacao = None
        erro_notificacao = None
        if riscos:
            try:
                notificacao = notificador.notificar(dispositivo, riscos, leitura)
            except OSError as erro:  # Inclui smtplib.SMTPException e falhas de rede
                log.exception("Falha ao enviar alerta")
                erro_notificacao = str(erro)

        return jsonify(
            nivel=nivel,
            riscos=[{"codigo": r.codigo, "nivel": r.nivel, "explicacao": r.explicacao} for r in riscos],
            notificacao=notificacao,
            erro_notificacao=erro_notificacao,
        ), 201

    def consultar(colecao):
        dispositivo = request.args.get("dispositivo")
        if not dispositivo:
            return jsonify(erros=["informe ?dispositivo="]), 400
        with trava:
            itens = list(colecao.get(dispositivo, ()))
        return jsonify(itens[-limite_da_consulta():])

    @app.get("/api/v1/leituras")
    def listar_leituras():
        return consultar(leituras)

    @app.get("/api/v1/alertas")
    def listar_alertas():
        return consultar(alertas)

    @app.get("/api/v1/saude")
    def saude():
        return jsonify(status="ok", email="smtp" if notificador.host else "simulacao")

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    criar_app().run(host="127.0.0.1", port=5000)
