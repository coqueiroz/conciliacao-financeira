"""Envio do resultado da conciliação por e-mail (Gmail via SMTP)."""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage
from html import escape
from pathlib import Path

import pandas as pd

from conciliacao.pipeline import indicadores
from conciliacao.relatorio import ORDEM_SITUACOES

log = logging.getLogger(__name__)



def carregar_env(caminho: Path) -> None:
    """Lê um arquivo .env simples (CHAVE=valor) para as variáveis de ambiente."""
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            chave, valor = linha.split("=", 1)
            os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def moeda(valor: float) -> str:
    texto = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-R$ {texto}" if valor < 0 else f"R$ {texto}"


def montar_html(resultado: pd.DataFrame, invalidos: pd.DataFrame, data_referencia: str) -> str:
    """Corpo do e-mail em HTML (estilos inline, como os clientes de e-mail exigem)."""
    ind = indicadores(resultado)
    data_br = pd.Timestamp(data_referencia).strftime("%d/%m/%Y")

    linhas = ""
    for situacao in ORDEM_SITUACOES:
        grupo = resultado[resultado["situacao"] == situacao]
        if grupo.empty:
            continue
        destaque = "" if situacao == "Conciliado" else "font-weight:bold;"
        linhas += (
            f'<tr><td style="padding:6px 10px;border-bottom:1px solid #e5e5e5;{destaque}">{situacao}</td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #e5e5e5;text-align:right">{len(grupo)}</td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #e5e5e5;text-align:right">'
            f'{moeda(grupo["diferenca"].sum())}</td></tr>'
        )

    abertas = (resultado[resultado["situacao"] == "Venda sem pagamento"]
               .sort_values("dias_em_aberto", ascending=False).head(5))
    lista_abertas = "".join(
        f"<li>{escape(str(r.codigo_venda))} — {escape(str(r.cliente))} — {moeda(r.valor_venda)} "
        f"({int(r.dias_em_aberto)} dias em aberto)</li>"
        for r in abertas.itertuples()
    )

    aviso_invalidos = ""
    if not invalidos.empty:
        aviso_invalidos = (f'<p style="color:#a15c00">Atenção: {len(invalidos)} linha(s) dos arquivos de entrada '
                           f'tinham dados inválidos e ficaram de fora. Veja a aba "Dados inválidos".</p>')

    return f"""\
<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#222;max-width:620px">
  <h2 style="color:#1F3A5F;margin-bottom:4px">Conciliação financeira — {data_br}</h2>
  <p style="margin-top:0"><b>{ind['vendas_conciliadas']} de {ind['vendas_faturadas']}</b> vendas conciliadas
     ({ind['percentual_conciliado']:.0%}). <b>{ind['pendencias']}</b> pendência(s) para analisar e
     <b>{moeda(ind['valor_em_aberto'])}</b> em vendas sem pagamento.</p>
  <table style="border-collapse:collapse;width:100%">
    <tr style="background:#1F3A5F;color:#fff">
      <th style="padding:8px 10px;text-align:left">Situação</th>
      <th style="padding:8px 10px;text-align:right">Qtd.</th>
      <th style="padding:8px 10px;text-align:right">Diferença</th>
    </tr>
    {linhas}
  </table>
  {f'<p style="margin-top:18px"><b>Vendas sem pagamento há mais tempo:</b></p><ul>{lista_abertas}</ul>' if lista_abertas else ''}
  {aviso_invalidos}
  <p>O relatório completo, com uma aba para cada pendência, está em anexo.</p>
  <p style="color:#888;font-size:12px">Mensagem gerada automaticamente pelo sistema de conciliação.</p>
</div>"""


def enviar_email(html: str, anexo: Path, assunto: str, destinatarios: list[str]) -> None:
    """Envia o e-mail pelo Gmail. Requer GMAIL_USUARIO e GMAIL_SENHA_APP no ambiente ou no .env."""
    usuario = os.environ.get("GMAIL_USUARIO")
    senha = os.environ.get("GMAIL_SENHA_APP")
    if not usuario or not senha:
        raise RuntimeError("Defina GMAIL_USUARIO e GMAIL_SENHA_APP no arquivo .env (veja .env.exemplo).")

    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = usuario
    msg["To"] = ", ".join(destinatarios)
    msg.set_content("Seu cliente de e-mail não exibe HTML. O relatório completo está em anexo.")
    msg.add_alternative(html, subtype="html")
    msg.add_attachment(
        anexo.read_bytes(),
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=anexo.name,
    )

    # Gmail por padrão; outro provedor (ex.: Outlook) pode ser usado definindo SMTP_SERVIDOR e SMTP_PORTA
    servidor = os.environ.get("SMTP_SERVIDOR", "smtp.gmail.com")
    porta = int(os.environ.get("SMTP_PORTA", "465"))
    if porta == 465:
        with smtplib.SMTP_SSL(servidor, porta, timeout=30) as smtp:
            smtp.login(usuario, senha)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(servidor, porta, timeout=30) as smtp:
            if smtp.has_extn("starttls"):
                smtp.starttls()
                smtp.ehlo()
            if smtp.has_extn("auth"):
                smtp.login(usuario, senha)
            smtp.send_message(msg)
    log.info("E-mail enviado para %s", ", ".join(destinatarios))
