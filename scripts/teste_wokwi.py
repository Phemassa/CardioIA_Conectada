"""Roda o roteiro de teste do firmware no Wokwi real, com o dashboard aberto, e gera evidencias.

Monta o projeto em wokwi.com sem login, comanda a simulacao como uma pessoa faria e confere
o Monitor Serial, os LEDs do circuito e o painel. Falha em vez de salvar um print enganoso.
Depende da interface do Wokwi: se o site mudar, os seletores podem precisar de ajuste.

Pre-requisito: Node-RED rodando (cd dashboard/node-red && npm start).
Uso: python scripts/teste_wokwi.py [--salvar "Nome do projeto"]
Com --salvar, em vez do teste, salva o projeto como publico e imprime o link (nao listado e pago).
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
FW = RAIZ / "firmware" / "sketch"
SAIDA = RAIZ / "assets" / "evidencias"
URL_WOKWI = "https://wokwi.com/projects/new/esp32"
URL_PAINEL = "http://localhost:1880/ui/"


def definir_conteudo(pg, texto):
    pg.evaluate("""t => {
        const ed = monaco.editor.getEditors().find(e => e.getModel() && e.getDomNode().offsetParent);
        ed.getModel().setValue(t);
    }""", texto)


def novo_arquivo(pg, nome):
    # O menu de arquivos e o ultimo icone da barra de abas, que pode quebrar em duas linhas.
    pos = pg.evaluate("""() => {
        const itens = [...document.querySelectorAll('svg, button')]
            .map(e => e.getBoundingClientRect())
            .filter(r => r.width > 0 && r.top > 44 && r.bottom < 112 && r.left < 750);
        const r = itens.sort((a, b) => (b.top - a.top) || (b.left - a.left))[0];
        return [r.left + r.width / 2, r.top + r.height / 2];
    }""")
    pg.mouse.click(*pos)
    pg.wait_for_timeout(900)
    pg.get_by_text("New file", exact=False).first.click()
    pg.wait_for_timeout(700)
    pg.keyboard.press("Control+A")  # O dialogo conserva o nome digitado antes
    pg.keyboard.type(nome)
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(1500)


def montar_projeto(pg):
    pg.goto(URL_WOKWI, wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_function("window.monaco && monaco.editor.getEditors().length > 0", timeout=90000)
    pg.wait_for_timeout(4000)
    definir_conteudo(pg, (FW / "sketch.ino").read_text(encoding="utf8"))
    pg.get_by_text("diagram.json", exact=True).first.click()
    pg.wait_for_timeout(1500)
    definir_conteudo(pg, (FW / "diagram.json").read_text(encoding="utf8"))
    pg.wait_for_timeout(1500)

    # Instalar uma biblioteca pela interface cria a aba libraries.txt, editada em seguida.
    pg.get_by_text("Library Manager", exact=True).first.click()
    pg.wait_for_timeout(800)
    pg.mouse.click(710, 119)
    pg.wait_for_timeout(1000)
    pg.keyboard.type("PubSubClient")
    pg.wait_for_timeout(2500)
    pg.get_by_text("PubSubClient", exact=True).first.click()
    pg.wait_for_timeout(1500)
    pg.get_by_text("libraries.txt", exact=True).first.click()
    pg.wait_for_timeout(1000)
    definir_conteudo(pg, (FW / "libraries.txt").read_text(encoding="utf8"))
    pg.wait_for_timeout(1000)

    for nome in ("config.h", "edge_logic.h"):
        novo_arquivo(pg, nome)
        definir_conteudo(pg, (FW / nome).read_text(encoding="utf8"))
        pg.wait_for_timeout(800)


class Simulacao:
    """Controla a simulacao e acumula o Monitor Serial, que pode descartar linhas antigas."""

    def __init__(self, pg):
        self.pg = pg
        self.linhas = []

    def coletar(self):
        texto = self.pg.evaluate("document.body.innerText")
        inicio = texto.rfind("ets Jul 29")
        if inicio < 0:
            if self.linhas:  # O Monitor descartou o inicio: o historico deixaria de ser confiavel
                raise AssertionError("Monitor Serial descartou linhas antigas")
            return
        atuais = texto[inicio:].splitlines()
        # Depois da ultima linha do firmware vem texto da interface.
        ultima = max((i for i, l in enumerate(atuais) if l.startswith("[")), default=-1)
        self.linhas = atuais[:ultima + 1]

    def esperar(self, descricao, condicao, timeout_s):
        limite = time.time() + timeout_s
        while time.time() < limite:
            self.coletar()
            if condicao(self.linhas):
                print(f"OK {descricao}", flush=True)
                return True
            self.pg.wait_for_timeout(1000)
        raise AssertionError(f"{descricao}: nao ocorreu em {timeout_s} s")

    def enviar(self, comando):
        # Campo do Monitor Serial: a unica entrada de texto na metade direita da tela.
        campo = self.pg.locator('input:not([type]), input[type="text"]').last
        campo.click()
        campo.fill(comando)
        campo.press("Enter")

    def clicar_parte(self, seletor):
        c = self.pg.locator(seletor).first.bounding_box()
        self.pg.mouse.click(c["x"] + c["width"] / 2, c["y"] + c["height"] / 2)

    def ajustar_sensor(self, seletor, valores):
        """Abre o painel do sensor e move os controles deslizantes: {indice: valor}."""
        self.clicar_parte(seletor)
        self.pg.wait_for_timeout(1000)
        self.pg.evaluate("""valores => {
            const faixas = [...document.querySelectorAll('input[type=range]')];
            const definir = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
            for (const [i, v] of Object.entries(valores)) {
                definir.call(faixas[i], v);
                faixas[i].dispatchEvent(new Event('input', {bubbles: true}));
                faixas[i].dispatchEvent(new Event('change', {bubbles: true}));
            }
        }""", {str(k): str(v) for k, v in valores.items()})
        self.pg.wait_for_timeout(500)
        self.pg.keyboard.press("Escape")
        self.pg.mouse.click(1000, 120)  # Clica em area vazia para fechar o painel
        self.pg.wait_for_timeout(500)

    def led(self, indice):
        return self.pg.evaluate(f"!!document.querySelectorAll('wokwi-led')[{indice}].value")


def leituras(linhas):
    saida = []
    for l in linhas:
        m = re.search(r"\[LEITURA\] seq=(\d+) t=([\d.]+)C .*bpm=(\d+) mov=(\d+)mg flags=0x(\w+) fila=(\d+)/", l)
        if m:
            saida.append({"seq": int(m[1]), "t": float(m[2]), "bpm": int(m[3]), "mov": int(m[4]),
                          "flags": int(m[5], 16), "fila": int(m[6])})
    return saida


def nuvem(linhas):
    """Junta as mensagens [CLOUD], que o Monitor pode quebrar em varias linhas."""
    saida, atual = [], None
    for l in linhas:
        if l.startswith("[CLOUD] "):
            atual = l[8:]
        elif atual is not None:
            atual += l
        else:
            continue
        try:
            saida.append(json.loads(atual))
            atual = None
        except json.JSONDecodeError:
            if not atual.lstrip().startswith("{") or len(atual) > 400:
                atual = None
    return saida


def testar(pg, painel):
    sim = Simulacao(pg)
    print_w = lambda nome: pg.screenshot(path=SAIDA / nome)

    def print_p(nome, led=None, texto=None):
        painel.bring_to_front()
        if led:
            painel.wait_for_selector(f"#led-indicador.{led}", timeout=30000)
        if texto:
            painel.wait_for_function("t => document.body.innerText.includes(t)", arg=texto, timeout=30000)
        painel.wait_for_timeout(1500)
        painel.screenshot(path=SAIDA / nome)
        pg.bring_to_front()

    def ultima(linhas):
        l = leituras(linhas)
        return l[-1] if l else {"seq": -1, "t": 0, "bpm": 0, "mov": 0, "flags": 0, "fila": 0}

    pg.mouse.click(778, 108)  # Iniciar simulacao
    sim.esperar("Firmware iniciou", lambda l: any("Wearable iniciando" in x for x in l), 240)
    sim.esperar("MQTT conectado ao broker", lambda l: any("MQTT conectado" in x for x in l), 90)

    # Aceleracao constante diferente de 1 g mantem o paciente "em movimento" durante o roteiro.
    sim.ajustar_sensor("wokwi-mpu6050", {2: 1.5})
    sim.esperar("MPU6050 detecta movimento", lambda l: ultima(l)["mov"] >= 50, 30)

    sim.enviar("b80")
    sim.esperar("Leitura de 80 bpm", lambda l: 75 <= ultima(l)["bpm"] <= 85 and ultima(l)["flags"] == 0, 30)
    print_w("wokwi_circuito.png")
    print_p("dashboard_esp32_normal.png", led="led-normal")
    assert not sim.led(0), "LED vermelho aceso em ritmo normal"
    assert not sim.led(1), "LED amarelo aceso com conexao ativa"
    print_w("wokwi_serial_online.png")

    sim.enviar("b130")
    sim.esperar("Taquicardia detectada no edge", lambda l: ultima(l)["flags"] & 1, 30)
    pg.wait_for_timeout(500)
    assert sim.led(0), "LED vermelho deveria acender na taquicardia"
    print("OK LED vermelho aceso", flush=True)
    print_w("wokwi_alerta_taquicardia.png")
    print_p("dashboard_esp32_taquicardia.png", led="led-critico", texto="TAQUICARDIA")

    sim.enviar("b80")
    sim.esperar("Ritmo normalizou", lambda l: ultima(l)["flags"] == 0, 30)
    sim.ajustar_sensor("wokwi-dht22", {0: 38.6})
    sim.esperar("Febre detectada no edge", lambda l: ultima(l)["t"] > 38 and ultima(l)["flags"] & 4, 30)
    print_p("dashboard_esp32_febre.png", led="led-critico", texto="FEBRE")
    sim.ajustar_sensor("wokwi-dht22", {0: 36.6})
    sim.esperar("Temperatura normalizou", lambda l: ultima(l)["flags"] == 0, 30)

    # Queda de conexao, com uma taquicardia acontecendo durante o periodo offline.
    sim.enviar("b130")
    sim.clicar_parte("wokwi-slide-switch")
    sim.esperar("Switch desconectou", lambda l: any("Wi-Fi simulado: DESCONECTADO" in x for x in l), 15)
    sim.esperar("Fila cresce offline", lambda l: ultima(l)["fila"] >= 6, 90)
    pg.wait_for_timeout(500)
    assert sim.led(1), "LED amarelo deveria acender offline"
    assert sim.led(0), "Alerta deve continuar funcionando offline"
    print("OK LEDs amarelo e vermelho acesos sem conexao", flush=True)
    print_w("wokwi_serial_offline.png")
    print_p("dashboard_esp32_offline.png", texto="Offline")
    retidas = ultima(sim.linhas)["fila"]
    primeira_replay = ultima(sim.linhas)["seq"] - retidas + 1

    sim.enviar("b80")
    sim.clicar_parte("wokwi-slide-switch")
    sim.esperar("Replay chegou a nuvem", lambda l: any(m.get("replay") for m in nuvem(l)), 60)
    sim.esperar("Fila esvaziou", lambda l: any(m.get("replay") for m in nuvem(l)) and ultima(l)["fila"] <= 1, 60)
    # O Monitor ja rolou: volta ate a primeira mensagem de replay para o print mostra-la.
    pg.mouse.move(1100, 830)
    pg.mouse.wheel(0, -260)
    pg.wait_for_timeout(400)
    print_w("wokwi_serial_sync.png")
    print_p("dashboard_esp32_replay.png", texto="Recuperado do buffer")

    # Nenhuma amostra pode se perder ou repetir: sequencia continua do inicio ao fim.
    (SAIDA / "wokwi_monitor_serial.txt").write_text("\n".join(sim.linhas) + "\n", encoding="utf8", newline="\n")
    seqs =[m["seq"] for m in nuvem(sim.linhas)]
    assert seqs == sorted(set(seqs)), f"Amostras repetidas ou fora de ordem: {seqs}"
    faltando = sorted(set(range(primeira_replay, seqs[-1] + 1)) - set(seqs))
    assert not faltando, f"Amostras perdidas na queda: {faltando}"
    replay = [m for m in nuvem(sim.linhas) if m["replay"]]
    assert any("TAQUICARDIA" in m["alertas"] for m in replay), "Alerta offline nao foi recuperado"
    print(f"OK {retidas} amostras retidas, nenhuma perdida; {len(replay)} marcadas como replay, "
          f"idade maxima {max(m['age_s'] for m in replay)} s", flush=True)

    # Batimentos reais pelo botao, sem o comando de simulacao.
    sim.enviar("b0")
    sim.pg.wait_for_timeout(6000)
    caixa = pg.locator("wokwi-pushbutton").first.bounding_box()
    cx, cy = caixa["x"] + caixa["width"] / 2, caixa["y"] + caixa["height"] * 0.4
    antes = ultima(sim.linhas)["seq"]
    for _ in range(14):
        pg.mouse.move(cx, cy)
        pg.mouse.down()
        pg.wait_for_timeout(100)
        pg.mouse.up()
        pg.wait_for_timeout(650)
    sim.esperar("Botao gera BPM", lambda l: ultima(l)["seq"] > antes and ultima(l)["bpm"] > 0, 12)
    print(f"   BPM pelo botao: {ultima(sim.linhas)['bpm']}", flush=True)

    # Paciente parado: acelerometro de volta a 1 g por mais de 2 minutos.
    sim.ajustar_sensor("wokwi-mpu6050", {2: 1})
    sim.enviar("b80")
    sim.esperar("Imobilidade apos 2 min sem movimento", lambda l: ultima(l)["flags"] & 8, 170)
    print_p("dashboard_esp32_imobilidade.png", led="led-atencao", texto="IMOBILIDADE")
    assert not sim.led(0), "Imobilidade e atencao: nao deve acender o LED vermelho"
    print("OK Imobilidade nao acende o LED vermelho", flush=True)

    sim.enviar("s")
    sim.esperar("Comando de status", lambda l: any("[STATUS]" in x for x in l), 15)
    sim.coletar()
    print([x for x in sim.linhas if "[STATUS]" in x][-1], flush=True)
    (SAIDA / "wokwi_monitor_serial.txt").write_text("\n".join(sim.linhas) + "\n", encoding="utf8", newline="\n")


def salvar(pg, nome):
    montar_projeto(pg)
    pg.mouse.click(146, 19)
    pg.wait_for_timeout(1500)
    pg.get_by_label("Project Name").fill(nome)
    pg.wait_for_timeout(500)
    pg.get_by_role("button", name=re.compile("^save$", re.I)).last.click()
    pg.wait_for_url(re.compile(r"/projects/\d+"), timeout=60000)
    print("LINK", pg.url, flush=True)


def main() -> int:
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--salvar", metavar="NOME")
    args.add_argument("--canal", default="msedge")
    args = args.parse_args()
    sys.stdout.reconfigure(encoding="utf8")
    SAIDA.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        navegador = p.chromium.launch(channel=args.canal, headless=True)
        pg = navegador.new_page(viewport={"width": 1500, "height": 950})
        try:
            if args.salvar:
                salvar(pg, args.salvar)
                return 0
            painel = navegador.new_page(viewport={"width": 1400, "height": 800})
            painel.goto(URL_PAINEL)
            painel.wait_for_selector("#led-indicador", timeout=30000)
            pg.bring_to_front()
            montar_projeto(pg)
            testar(pg, painel)
            print("TODOS OS PASSOS PASSARAM", flush=True)
            return 0
        except Exception as erro:
            pg.screenshot(path=SAIDA / "falha_wokwi.png")
            print("FALHOU:", str(erro)[:500], flush=True)
            return 1
        finally:
            navegador.close()


if __name__ == "__main__":
    raise SystemExit(main())
