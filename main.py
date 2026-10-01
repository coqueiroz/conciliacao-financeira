"""
Conciliação financeira automática: vendas x extrato bancário.

Uso:
    python main.py --data-referencia 2026-09-30
    python main.py --data-referencia 2026-09-30 --enviar-email
    python main.py --vendas caminho/vendas.xlsx --extrato caminho/extrato.csv --enviar-email --para financeiro@empresa.com
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path

from conciliacao import notificacao, pipeline, relatorio

RAIZ = Path(__file__).resolve().parent


def configurar_log(pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%d/%m/%Y %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(pasta / "execucao.log", encoding="utf-8"),
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Concilia vendas com o extrato bancário.")
    parser.add_argument("--vendas", type=Path, default=RAIZ / "dados/entrada/vendas.xlsx")
    parser.add_argument("--extrato", type=Path, default=RAIZ / "dados/entrada/extrato_bancario.csv")
    parser.add_argument("--saida", type=Path, default=RAIZ / "saida")
    parser.add_argument("--data-referencia", default=date.today().isoformat(),
                        help="Data usada para calcular os dias em aberto (AAAA-MM-DD).")
    parser.add_argument("--tolerancia", type=float, default=0.0,
                        help="Diferença máxima aceita entre venda e pagamento, em reais.")
    parser.add_argument("--enviar-email", action="store_true",
                        help="Envia o resumo e o relatório por e-mail (configure o .env antes).")
    parser.add_argument("--para", nargs="+",
                        help="Destinatário(s) do e-mail. Padrão: EMAIL_DESTINO do .env ou o próprio remetente.")
    args = parser.parse_args()

    configurar_log(args.saida)
    log = logging.getLogger("main")
    notificacao.carregar_env(RAIZ / ".env")

    for arquivo in (args.vendas, args.extrato):
        if not arquivo.exists():
            log.error("Arquivo não encontrado: %s (rode 'python dados/gerar_dados.py' para criar os exemplos)", arquivo)
            return 1

    resultado, invalidos = pipeline.executar(
        args.vendas, args.extrato, args.data_referencia, args.tolerancia,
        caminho_banco=args.saida / "conciliacao.db",
    )

    caminho_relatorio = args.saida / f"conciliacao_{args.data_referencia}.xlsx"
    relatorio.gerar_excel(resultado, invalidos, caminho_relatorio, args.data_referencia)

    contagem = resultado["situacao"].value_counts()
    log.info("Resumo: %s", " | ".join(f"{s}: {q}" for s, q in contagem.items()))

    # o corpo do e-mail é sempre salvo, para conferir sem precisar enviar
    html = notificacao.montar_html(resultado, invalidos, args.data_referencia)
    previa = args.saida / "email_previa.html"
    previa.write_text(html, encoding="utf-8")
    log.info("Prévia do e-mail salva em %s", previa)

    if args.enviar_email:
        destinatarios = args.para or [os.environ.get("EMAIL_DESTINO") or os.environ.get("GMAIL_USUARIO", "")]
        ind = pipeline.indicadores(resultado)
        assunto = (f"Conciliação {args.data_referencia}: {ind['pendencias']} pendência(s), "
                   f"{ind['percentual_conciliado']:.0%} conciliado")
        try:
            notificacao.enviar_email(html, caminho_relatorio, assunto, destinatarios)
        except Exception as erro:  # o relatório já foi gerado; só o envio falhou
            log.error("Não foi possível enviar o e-mail: %s", erro)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
