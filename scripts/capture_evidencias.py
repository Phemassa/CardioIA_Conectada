"""Roda o roteiro do simulador contra o dashboard real e gera prints em assets/evidencias.

Em cada cenario confere o estado do LED virtual; se o painel nao reagir como esperado,
o script falha em vez de salvar um print enganoso.

Pre-requisito: Node-RED rodando (cd dashboard/node-red && npm start).
Usa o Microsoft Edge instalado; troque com --canal chrome.
"""
import argparse
import subprocess
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "assets" / "evidencias"
URL = "http://localhost:1880/ui/"

# cenario do simulador -> (classe esperada do LED, texto esperado na pagina, arquivo)
ETAPAS = {
    "Normal": ("led-normal", "Normal", "dashboard_01_normal.png"),
    "Taquicardia": ("led-critico", "TAQUICARDIA", "dashboard_02_taquicardia.png"),
    "Febre": ("led-critico", "FEBRE", "dashboard_03_febre.png"),
    "Offline com taquicardia no buffer": (None, "Offline", "dashboard_04_offline.png"),
    "Normal apos reconexao": ("led-normal", "Recuperado do buffer", "dashboard_05_replay.png"),
    "Imobilidade": ("led-atencao", "IMOBILIDADE", "dashboard_06_imobilidade.png"),
}


def paineis_sobrepostos(pagina) -> list:
    """Grupos do dashboard que se cobrem: defeito visual que as outras checagens nao veem."""
    return pagina.evaluate("""() => {
        const caixas = [...document.querySelectorAll('.nr-dashboard-cardpanel')]
            .map(el => ({r: el.getBoundingClientRect(), nome: el.innerText.trim().slice(0, 25)}));
        const pares = [];
        caixas.forEach((a, i) => caixas.slice(i + 1).forEach(b => {
            if (a.r.left < b.r.right && b.r.left < a.r.right &&
                a.r.top < b.r.bottom && b.r.top < a.r.bottom) pares.push(a.nome + ' x ' + b.nome);
        }));
        return pares;
    }""")


def main() -> int:
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--canal", default="msedge")
    args = args.parse_args()
    SAIDA.mkdir(parents=True, exist_ok=True)

    sim = subprocess.Popen(
        [sys.executable, "-u", str(RAIZ / "scripts" / "simula_esp32.py")],
        stdout=subprocess.PIPE, text=True,
    )
    cenarios = []
    novo_cenario = threading.Event()

    def ler_simulador():
        for linha in sim.stdout:
            print("[sim]", linha.strip(), flush=True)
            if linha.startswith("== "):
                cenarios.append(linha[3:].strip())
                novo_cenario.set()

    threading.Thread(target=ler_simulador, daemon=True).start()

    erros = []
    with sync_playwright() as p:
        navegador = p.chromium.launch(channel=args.canal, headless=True)
        pagina = navegador.new_page(viewport={"width": 1400, "height": 1000})
        pagina.goto(URL)
        pagina.wait_for_selector("#led-indicador", timeout=30000)
        if len(pagina.query_selector_all(".nr-dashboard-cardpanel")) < 2:
            erros.append("Paineis do dashboard nao encontrados")

        vistos = 0
        while vistos < len(ETAPAS):
            if not novo_cenario.wait(timeout=60):
                erros.append("Simulador parou antes de concluir o roteiro")
                break
            novo_cenario.clear()
            while vistos < len(cenarios):
                nome = cenarios[vistos]
                vistos += 1
                classe, texto, arquivo = ETAPAS[nome]
                try:
                    if classe:
                        pagina.wait_for_selector(f"#led-indicador.{classe}", timeout=20000)
                    pagina.wait_for_function(
                        "t => document.body.innerText.includes(t)", arg=texto, timeout=25000)
                    if nome == "Normal apos reconexao":
                        # Espera a fila terminar de esvaziar antes de fotografar.
                        pagina.wait_for_function(
                            "() => document.body.innerText.includes('0 na fila')", timeout=20000)
                    pagina.wait_for_timeout(5000)  # Acumula pontos no grafico
                    if sobrepostos := paineis_sobrepostos(pagina):
                        erros.append(f"{nome}: paineis sobrepostos {sobrepostos}")
                    pagina.screenshot(path=SAIDA / arquivo)
                    print(f"OK {nome}: {arquivo}", flush=True)
                except Exception as erro:
                    erros.append(f"{nome}: {str(erro).splitlines()[0]}")

        sim.wait(timeout=120)
        # Sem novas leituras, o watchdog tem de sair do ultimo estado e avisar.
        try:
            pagina.wait_for_selector("#led-indicador.led-semdados", timeout=40000)
            pagina.screenshot(path=SAIDA / "dashboard_07_sem_dados.png")
            print("OK Watchdog: dashboard_07_sem_dados.png", flush=True)
        except Exception as erro:
            erros.append(f"Watchdog: {str(erro).splitlines()[0]}")
        navegador.close()

    for erro in erros:
        print("ERRO", erro)
    return 1 if erros else 0


if __name__ == "__main__":
    raise SystemExit(main())
