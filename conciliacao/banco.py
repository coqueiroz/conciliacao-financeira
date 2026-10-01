"""Criação do banco SQLite, carga dos dados e execução da conciliação em SQL."""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

PASTA_SQL = Path(__file__).resolve().parent.parent / "sql"


def conectar(caminho: str | Path = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(caminho)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def criar_tabelas(conn: sqlite3.Connection) -> None:
    conn.executescript((PASTA_SQL / "schema.sql").read_text(encoding="utf-8"))


def carregar(conn: sqlite3.Connection, vendas: pd.DataFrame, lancamentos: pd.DataFrame) -> None:
    """Insere vendas e lançamentos numa única transação (tudo ou nada)."""
    with conn:
        conn.executemany(
            """INSERT INTO vendas (codigo, data_venda, cliente, valor_centavos, forma_pagamento, status)
               VALUES (:codigo, :data_venda, :cliente, :valor_centavos, :forma_pagamento, :status)""",
            vendas.to_dict("records"),
        )
        conn.executemany(
            """INSERT INTO lancamentos (data_lancamento, historico, documento, valor_centavos, referencia_venda)
               VALUES (:data_lancamento, :historico, :documento, :valor_centavos, :referencia_venda)""",
            lancamentos.to_dict("records"),
        )
    log.info("Banco carregado: %d vendas e %d lançamentos", len(vendas), len(lancamentos))


def conciliar(conn: sqlite3.Connection, data_referencia: str, tolerancia_centavos: int = 0) -> pd.DataFrame:
    """Executa sql/conciliacao.sql e devolve o resultado com valores em reais."""
    consulta = (PASTA_SQL / "conciliacao.sql").read_text(encoding="utf-8")
    resultado = pd.read_sql_query(
        consulta, conn,
        params={"data_referencia": data_referencia, "tolerancia_centavos": tolerancia_centavos},
    )
    # diferença calculada em centavos (inteiros) e só depois convertida para reais
    resultado["diferenca"] = resultado["valor_pago"].fillna(0) - resultado["valor_venda"].fillna(0)
    for coluna in ("valor_venda", "valor_pago", "diferenca"):
        resultado[coluna] = resultado[coluna] / 100
    for coluna in ("data_venda", "data_pagamento"):
        resultado[coluna] = pd.to_datetime(resultado[coluna])
    return resultado
