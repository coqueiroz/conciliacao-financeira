"""Leitura, limpeza e validação dos arquivos de entrada."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

log = logging.getLogger(__name__)

PADRAO_REFERENCIA = re.compile(r"\bVND-\d{5}\b")


def valor_br_para_centavos(texto) -> Optional[int]:
    """Converte '1.234,56', 'R$ 89,90' ou '-59,90' em centavos (int).

    Retorna None quando o valor está vazio ou ilegível.
    """
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return None
    if isinstance(texto, (int, float)):
        return round(float(texto) * 100)
    limpo = str(texto).strip().replace("R$", "").replace(" ", "")
    if not limpo:
        return None
    limpo = limpo.replace(".", "").replace(",", ".")
    try:
        return round(float(limpo) * 100)
    except ValueError:
        return None


def data_br_para_iso(texto) -> Optional[str]:
    """Converte '05/09/2026' em '2026-09-05'. Retorna None se a data não existir."""
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return None
    if isinstance(texto, (datetime, pd.Timestamp)):
        return texto.strftime("%Y-%m-%d")
    try:
        return datetime.strptime(str(texto).strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def extrair_referencia(historico: str) -> Optional[str]:
    """Procura o código da venda (VND-00000) no histórico do extrato."""
    achado = PADRAO_REFERENCIA.search(str(historico).upper())
    return achado.group(0) if achado else None


MENSAGENS = {
    "codigo": "código da venda ausente",
    "data_venda": "data inválida",
    "data_lancamento": "data inválida",
    "valor_centavos": "valor vazio ou ilegível",
}


def _separar_invalidos(df: pd.DataFrame, colunas_obrigatorias: list[str], origem: str):
    """Divide o DataFrame em linhas válidas e inválidas (com o motivo)."""
    motivos = pd.Series("", index=df.index)
    for coluna in colunas_obrigatorias:
        motivos[df[coluna].isna()] += f"{MENSAGENS[coluna]}; "
    invalidos = df[motivos != ""].copy()
    invalidos["motivo"] = motivos[motivos != ""].str.rstrip("; ")
    invalidos["origem"] = origem
    return df[motivos == ""].copy(), invalidos


def ler_vendas(caminho: Path):
    """Lê a planilha de vendas e devolve (vendas_validas, linhas_invalidas)."""
    bruto = pd.read_excel(caminho, dtype=str)
    log.info("Vendas lidas: %d linhas de %s", len(bruto), caminho.name)

    df = pd.DataFrame({
        "linha_arquivo": bruto.index + 2,  # +2: cabeçalho e índice começando em 1
        "codigo": bruto["Código"].str.strip().str.upper(),
        "data_venda": bruto["Data"].map(data_br_para_iso),
        "cliente": bruto["Cliente"].str.strip().str.title(),
        "valor_centavos": bruto["Valor (R$)"].map(valor_br_para_centavos),
        "forma_pagamento": bruto["Forma de Pagamento"].str.strip(),
        "status": bruto["Status"].str.strip().str.title(),
    })

    validas, invalidas = _separar_invalidos(df, ["codigo", "data_venda", "valor_centavos"], "vendas.xlsx")

    duplicadas = validas["codigo"].duplicated(keep="first")
    if duplicadas.any():
        repetidas = validas[duplicadas].copy()
        repetidas["motivo"], repetidas["origem"] = "código de venda repetido", "vendas.xlsx"
        invalidas = pd.concat([invalidas, repetidas])
        validas = validas[~duplicadas]

    validas["valor_centavos"] = validas["valor_centavos"].astype(int)
    log.info("Vendas válidas: %d | inválidas: %d", len(validas), len(invalidas))
    return validas, invalidas


def ler_extrato(caminho: Path):
    """Lê o extrato bancário (CSV ';' em latin-1) e devolve (lancamentos_validos, linhas_invalidas)."""
    bruto = pd.read_csv(caminho, sep=";", encoding="latin-1", dtype=str)
    log.info("Extrato lido: %d linhas de %s", len(bruto), caminho.name)

    df = pd.DataFrame({
        "linha_arquivo": bruto.index + 2,
        "data_lancamento": bruto["Data"].map(data_br_para_iso),
        "historico": bruto["Histórico"].str.strip(),
        "documento": bruto["Documento"].str.strip(),
        "valor_centavos": bruto["Valor"].map(valor_br_para_centavos),
    })
    df["referencia_venda"] = df["historico"].map(extrair_referencia)

    validos, invalidos = _separar_invalidos(df, ["data_lancamento", "valor_centavos"], "extrato_bancario.csv")
    validos["valor_centavos"] = validos["valor_centavos"].astype(int)
    log.info("Lançamentos válidos: %d | inválidos: %d", len(validos), len(invalidos))
    return validos, invalidos
