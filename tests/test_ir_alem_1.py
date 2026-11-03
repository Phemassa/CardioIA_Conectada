"""Testes do Ir Alem 1: risco, API, cliente REST e envio real por socket SMTP local."""
import email
import json
import re
import threading
from email import policy
from pathlib import Path
from werkzeug.serving import make_server

import pytest
from aiosmtpd.controller import Controller

from services import risco
from services.api_rest import criar_app
from services.cliente_rest import ClienteCardioIA, gerar_cenario
from services.email_alerta import INTERVALO_REENVIO_S, NotificadorEmail

RAIZ = Path(__file__).resolve().parent.parent


def codigos(riscos):
    return [r.codigo for r in riscos]


@pytest.mark.parametrize("bpm,temp,esperado", [
    (120, 38.0, []),                         # No limite ainda nao e alerta
    (121, 37.0, ["TAQUICARDIA"]),
    (50, 37.0, []),
    (49, 37.0, ["BRADICARDIA"]),
    (0, 37.0, []),                           # Sem sinal nao e bradicardia
    (80, 38.1, ["FEBRE"]),
    (130, 39.0, ["TAQUICARDIA", "FEBRE"]),
    (None, None, []),                        # Sensor sem leitura nao gera alerta
])
def test_limites(bpm, temp, esperado):
    assert codigos(risco.avaliar(bpm, temp)) == esperado


def test_imobilidade_exige_a_janela_inteira():
    n = risco.LEITURAS_PARA_IMOBILIDADE
    assert codigos(risco.avaliar(70, 36.5, [10] * n)) == ["IMOBILIDADE"]
    assert codigos(risco.avaliar(70, 36.5, [10] * (n - 1))) == []
    assert codigos(risco.avaliar(70, 36.5, [10] * (n - 1) + [60])) == []
    # Lacuna de sensor nao comprova imobilidade
    assert codigos(risco.avaliar(70, 36.5, [10] * (n - 1) + [None])) == []
    # Movimento antigo, fora da janela, nao impede o alerta
    assert codigos(risco.avaliar(70, 36.5, [300] + [10] * n)) == ["IMOBILIDADE"]


def test_nivel_geral():
    assert risco.nivel_geral([]) == risco.NORMAL
    assert risco.nivel_geral(risco.avaliar(70, 36.5, [10] * 24)) == risco.ATENCAO
    assert risco.nivel_geral(risco.avaliar(130, 36.5, [10] * 24)) == risco.CRITICO


@pytest.fixture
def api(tmp_path):
    notificador = NotificadorEmail(ambiente={}, pasta=tmp_path)
    return criar_app(notificador).test_client(), tmp_path


def post(cliente, **campos):
    return cliente.post("/api/v1/leituras", json={"dispositivo": "w1", **campos})


def test_api_registra_e_consulta(api):
    cliente, _ = api
    r = post(cliente, bpm=70, temp_c=36.5, umid_pct=55, mov_mg=100)
    assert r.status_code == 201 and r.json["nivel"] == "normal" and r.json["notificacao"] is None
    assert len(cliente.get("/api/v1/leituras?dispositivo=w1").json) == 1
    assert cliente.get("/api/v1/alertas?dispositivo=w1").json == []
    assert cliente.get("/api/v1/leituras?dispositivo=outro").json == []


@pytest.mark.parametrize("corpo", [
    [1, 2],
    {"bpm": 70},                              # Sem dispositivo
    {"dispositivo": "", "bpm": 70},
    {"dispositivo": "w1", "bpm": "70"},
    {"dispositivo": "w1", "bpm": True},
    {"dispositivo": "w1", "bpm": 300},
    {"dispositivo": "w1", "temp_c": 100},
])
def test_api_rejeita_leitura_invalida(api, corpo):
    cliente, _ = api
    assert cliente.post("/api/v1/leituras", json=corpo).status_code == 400
    assert cliente.get("/api/v1/leituras?dispositivo=w1").json == []


def test_api_exige_dispositivo_na_consulta(api):
    assert api[0].get("/api/v1/leituras").status_code == 400


def test_alerta_grava_email_sem_expor_dado_no_assunto(api):
    cliente, pasta = api
    r = post(cliente, bpm=140, temp_c=36.5)
    assert r.json["nivel"] == "critico" and r.json["notificacao"]
    arquivos = list(pasta.glob("*.eml"))
    assert len(arquivos) == 1
    msg = email.message_from_bytes(arquivos[0].read_bytes(), policy=policy.default)
    assert msg["Subject"] == "[CardioIA] TAQUICARDIA - w1"
    corpo = msg.get_content()
    assert "140 bpm" in corpo and "Nao usar para decisao clinica" in corpo


def test_pausa_entre_emails_por_tipo_de_risco(tmp_path):
    agora = [1000.0]
    n = NotificadorEmail(ambiente={}, pasta=tmp_path, relogio=lambda: agora[0])
    taqui = risco.avaliar(140, 36.5)
    ambos = risco.avaliar(140, 39.0)

    assert n.notificar("w1", taqui, {})
    assert n.notificar("w1", taqui, {}) is None        # Repetido: segura
    assert n.notificar("w2", taqui, {})                # Outro paciente: avisa
    assert n.notificar("w1", ambos, {})                # Febre nova: avisa, mesmo com a pausa
    agora[0] += INTERVALO_REENVIO_S - 1
    assert n.notificar("w1", taqui, {}) is None
    agora[0] += 1
    assert n.notificar("w1", taqui, {})                # Pausa venceu
    assert len(list(tmp_path.glob("*.eml"))) == 4


def test_falha_de_smtp_nao_perde_a_leitura_e_tenta_de_novo(tmp_path):
    notificador = NotificadorEmail(
        ambiente={"SMTP_HOST": "127.0.0.1", "SMTP_PORT": "1", "SMTP_STARTTLS": "0"}, pasta=tmp_path)
    cliente = criar_app(notificador).test_client()
    r = post(cliente, bpm=140)
    assert r.status_code == 201 and r.json["erro_notificacao"]
    assert len(cliente.get("/api/v1/leituras?dispositivo=w1").json) == 1
    # A falha nao conta como envio: a pausa nao pode calar a tentativa seguinte.
    assert post(cliente, bpm=141).json["erro_notificacao"]


class CaixaDeEntrada:
    def __init__(self):
        self.mensagens = []

    async def handle_DATA(self, server, session, envelope):
        self.mensagens.append(envelope)
        return "250 OK"


def test_ponta_a_ponta_http_e_smtp_reais():
    """Cliente -> HTTP real -> API -> SMTP real: nada simulado alem dos dados."""
    caixa = CaixaDeEntrada()
    smtp = Controller(caixa, hostname="127.0.0.1", port=8026)
    smtp.start()
    notificador = NotificadorEmail(ambiente={
        "SMTP_HOST": "127.0.0.1", "SMTP_PORT": "8026", "SMTP_STARTTLS": "0",
        "ALERTA_DESTINATARIO": "plantao@example.com",
    })
    servidor = make_server("127.0.0.1", 0, criar_app(notificador))
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    try:
        cliente = ClienteCardioIA(f"http://127.0.0.1:{servidor.server_port}")
        import random
        cenario = gerar_cenario(random.Random(42), "w1")
        respostas = [cliente.enviar_leitura(l) for l in cenario]

        assert len(cliente.listar_leituras("w1", 500)) == len(cenario)
        vistos = {r["codigo"] for resp in respostas for r in resp["riscos"]}
        assert vistos == {"TAQUICARDIA", "FEBRE", "IMOBILIDADE"}
        assert not any(resp["riscos"] for resp in respostas[:5])  # Fase normal nao alarma

        # 3 taquicardias e 3 febres, com a pausa, geram 1 e-mail cada; imobilidade, mais 1.
        assert len(caixa.mensagens) == 3
        assert caixa.mensagens[0].rcpt_tos == ["plantao@example.com"]
        assunto = email.message_from_bytes(caixa.mensagens[0].content, policy=policy.default)["Subject"]
        assert "TAQUICARDIA" in assunto
    finally:
        servidor.shutdown()
        smtp.stop()


def test_limites_iguais_em_firmware_e_node_red():
    """Os limites existem em 3 lugares; este teste impede que divirjam em silencio."""
    config = (RAIZ / "firmware/sketch/config.h").read_text(encoding="utf8")

    def define(nome):
        return int(re.search(rf"#define {nome} (\d+)", config).group(1))

    assert define("LIM_BPM_ALTO") == risco.BPM_ALTO
    assert define("LIM_BPM_BAIXO") == risco.BPM_BAIXO
    assert define("LIM_TEMP_FEBRE_DECIMOS") == risco.TEMP_FEBRE_C * 10
    assert define("LIM_MOV_MG") == risco.MOV_PARADO_MG
    intervalo_s = define("INTERVALO_AMOSTRA_MS") / 1000
    assert define("LIM_IMOBILIDADE_MS") / 1000 == risco.LEITURAS_PARA_IMOBILIDADE * intervalo_s

    fluxo = json.loads((RAIZ / "dashboard/node-red/flows.json").read_text(encoding="utf8"))
    fog = next(n for n in fluxo if n["id"] == "fn_fog")["func"]
    assert f"bpmAlto: {risco.BPM_ALTO}" in fog
    assert f"bpmBaixo: {risco.BPM_BAIXO}" in fog
    assert f"tempFebre: {risco.TEMP_FEBRE_C}" in fog
