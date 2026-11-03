"""Monta e dispara o e-mail de alerta (Ir Alem 1).

Sem SMTP_HOST configurado, roda em modo simulacao: grava o e-mail como .eml em
data/runtime/emails, que abre em qualquer cliente de e-mail. Com SMTP_HOST, envia de verdade.
"""
import os
import smtplib
import time
from email.message import EmailMessage
from pathlib import Path
from typing import Callable, Optional, Sequence

from services.risco import Risco

PASTA_SIMULACAO = Path(__file__).resolve().parent.parent / "data" / "runtime" / "emails"
# Durante uma crise o risco aparece em toda leitura; sem pausa, a equipe recebe um e-mail
# a cada 5 s e passa a ignora-los (fadiga de alarme).
INTERVALO_REENVIO_S = 300


def montar_email(dispositivo: str, riscos: Sequence[Risco], leitura: dict,
                 remetente: str, destinatario: str) -> EmailMessage:
    # Assunto aparece em notificacoes de tela bloqueada: so pseudonimo e tipo de alerta.
    codigos = ", ".join(r.codigo for r in riscos)
    msg = EmailMessage()
    msg["Subject"] = f"[CardioIA] {codigos} - {dispositivo}"
    msg["From"] = remetente
    msg["To"] = destinatario
    linhas = [
        f"Alerta automatico do dispositivo {dispositivo}.",
        "",
        *[f"- {r.codigo} ({r.nivel}): {r.explicacao}" for r in riscos],
        "",
        f"Batimentos: {leitura.get('bpm', '--')} bpm",
        f"Temperatura: {leitura.get('temp_c', '--')} °C",
        f"Movimento: {leitura.get('mov_mg', '--')} mg",
        "",
        "Projeto academico com dados simulados. Nao usar para decisao clinica.",
    ]
    msg.set_content("\n".join(linhas))
    return msg


class NotificadorEmail:
    """Aplica a pausa entre e-mails e escolhe entre SMTP real e simulacao."""

    def __init__(self, ambiente: Optional[dict] = None, pasta: Path = PASTA_SIMULACAO,
                 relogio: Callable[[], float] = time.time):
        amb = os.environ if ambiente is None else ambiente
        self.host = amb.get("SMTP_HOST", "")
        self.porta = int(amb.get("SMTP_PORT", "587"))
        self.usuario = amb.get("SMTP_USER", "")
        self.senha = amb.get("SMTP_PASSWORD", "")
        self.usar_tls = amb.get("SMTP_STARTTLS", "1") == "1"
        self.remetente = amb.get("ALERTA_REMETENTE", "cardioia@example.com")
        self.destinatario = amb.get("ALERTA_DESTINATARIO", "equipe-cardiologia@example.com")
        self.pasta = Path(pasta)
        self.relogio = relogio
        self._ultimo_envio: dict[tuple[str, str], float] = {}

    def notificar(self, dispositivo: str, riscos: Sequence[Risco], leitura: dict) -> Optional[str]:
        """Dispara se houver risco fora da pausa. Retorna onde o e-mail foi parar, ou None."""
        agora = self.relogio()
        # Pausa por tipo de risco: febre em plena taquicardia ainda precisa avisar.
        novos = [r for r in riscos
                 if agora - self._ultimo_envio.get((dispositivo, r.codigo), -INTERVALO_REENVIO_S)
                 >= INTERVALO_REENVIO_S]
        if not novos:
            return None

        msg = montar_email(dispositivo, novos, leitura, self.remetente, self.destinatario)
        destino = self._enviar_smtp(msg) if self.host else self._gravar_simulacao(msg, agora)
        # So registra depois de enviar: se o SMTP falhar, a proxima leitura tenta de novo.
        for r in novos:
            self._ultimo_envio[(dispositivo, r.codigo)] = agora
        return destino

    def _enviar_smtp(self, msg: EmailMessage) -> str:
        with smtplib.SMTP(self.host, self.porta, timeout=10) as smtp:
            if self.usar_tls:
                smtp.starttls()
            if self.usuario:
                smtp.login(self.usuario, self.senha)
            smtp.send_message(msg)
        return f"smtp://{self.host}:{self.porta}"

    def _gravar_simulacao(self, msg: EmailMessage, agora: float) -> str:
        self.pasta.mkdir(parents=True, exist_ok=True)
        base = f"alerta_{int(agora * 1000)}"
        caminho = self.pasta / f"{base}.eml"
        n = 1
        while caminho.exists():  # Dois alertas no mesmo milissegundo nao se sobrescrevem
            caminho = self.pasta / f"{base}_{n}.eml"
            n += 1
        caminho.write_bytes(bytes(msg))
        return str(caminho)
