"""Junta as etapas: extração -> banco -> conciliação. Usado pelo main.py e pelo painel."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from conciliacao import banco, extracao


def executar(vendas: Path, extrato: Path, data_referencia: str,
             tolerancia_reais: float = 0.0, caminho_banco: str | Path = ":memory:"):
    """Roda a conciliação completa e devolve (resultado, linhas_invalidas)."""
    vendas_ok, vendas_invalidas = extracao.ler_vendas(vendas)
    lancamentos_ok, lancamentos_invalidos = extracao.ler_extrato(extrato)

    conn = banco.conectar(caminho_banco)
    try:
        banco.criar_tabelas(conn)
        banco.carregar(conn, vendas_ok, lancamentos_ok)
        resultado = banco.conciliar(conn, data_referencia, round(tolerancia_reais * 100))
    finally:
        conn.close()

    invalidos = pd.concat([vendas_invalidas, lancamentos_invalidos], ignore_index=True)
    return resultado, invalidos


def indicadores(resultado: pd.DataFrame) -> dict:
    """Números principais usados no e-mail e no painel."""
    faturadas = resultado["valor_venda"].notna() & (resultado["situacao"] != "Venda cancelada com pagamento")
    conciliadas = int((resultado["situacao"] == "Conciliado").sum())
    total = int(faturadas.sum())
    em_aberto = resultado.loc[resultado["situacao"] == "Venda sem pagamento", "valor_venda"].sum()
    pendencias = int((resultado["situacao"] != "Conciliado").sum())
    return {
        "vendas_faturadas": total,
        "vendas_conciliadas": conciliadas,
        "percentual_conciliado": conciliadas / total if total else 0.0,
        "valor_em_aberto": round(float(em_aberto), 2),
        "pendencias": pendencias,
    }
