-- Estrutura do banco. Valores em CENTAVOS (inteiro) para evitar erros de
-- arredondamento de ponto flutuante (0,1 + 0,2 != 0,3).

DROP TABLE IF EXISTS vendas;
DROP TABLE IF EXISTS lancamentos;

CREATE TABLE vendas (
    codigo           TEXT PRIMARY KEY,
    data_venda       DATE    NOT NULL,
    cliente          TEXT    NOT NULL,
    valor_centavos   INTEGER NOT NULL CHECK (valor_centavos > 0),
    forma_pagamento  TEXT,
    status           TEXT    NOT NULL CHECK (status IN ('Faturada', 'Cancelada'))
);

CREATE TABLE lancamentos (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    data_lancamento  DATE    NOT NULL,
    historico        TEXT    NOT NULL,
    documento        TEXT,
    valor_centavos   INTEGER NOT NULL,          -- positivo = crédito, negativo = débito
    referencia_venda TEXT                       -- código VND-xxxxx encontrado no histórico
);

CREATE INDEX idx_lancamentos_referencia ON lancamentos (referencia_venda);
