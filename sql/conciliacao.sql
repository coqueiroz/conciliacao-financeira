-- Conciliação entre vendas e créditos do extrato.
-- Parâmetros: :tolerancia_centavos, :data_referencia (AAAA-MM-DD)
--
-- Resultado: uma linha por venda (exceto canceladas sem pagamento) e uma linha
-- por crédito que não corresponde a nenhuma venda, com a coluna "situacao".

WITH creditos AS (
    SELECT *
    FROM lancamentos
    WHERE valor_centavos > 0                    -- débitos (tarifas, fornecedores) ficam de fora
),

pagamentos_por_venda AS (
    SELECT
        referencia_venda,
        COUNT(*)                     AS qtd_pagamentos,
        SUM(valor_centavos)          AS total_pago,
        MIN(data_lancamento)         AS data_pagamento,
        GROUP_CONCAT(documento, ', ') AS documentos
    FROM creditos
    WHERE referencia_venda IS NOT NULL
    GROUP BY referencia_venda
)

SELECT
    v.codigo                                    AS codigo_venda,
    v.data_venda,
    v.cliente,
    v.valor_centavos                            AS valor_venda,
    p.total_pago                                AS valor_pago,
    p.qtd_pagamentos,
    p.data_pagamento,
    p.documentos,
    NULL                                        AS historico,
    CASE WHEN p.referencia_venda IS NULL
         THEN CAST(julianday(:data_referencia) - julianday(v.data_venda) AS INTEGER)
    END                                         AS dias_em_aberto,
    CASE
        WHEN v.status = 'Cancelada'                               THEN 'Venda cancelada com pagamento'
        WHEN p.referencia_venda IS NULL                            THEN 'Venda sem pagamento'
        WHEN p.qtd_pagamentos > 1                                  THEN 'Pagamento duplicado'
        WHEN ABS(p.total_pago - v.valor_centavos) > :tolerancia_centavos THEN 'Valor divergente'
        ELSE 'Conciliado'
    END                                         AS situacao
FROM vendas v
LEFT JOIN pagamentos_por_venda p ON p.referencia_venda = v.codigo
WHERE NOT (v.status = 'Cancelada' AND p.referencia_venda IS NULL)

UNION ALL

-- créditos sem venda correspondente (sem código no histórico ou com código inexistente)
SELECT
    c.referencia_venda,
    NULL,
    NULL,
    NULL,
    c.valor_centavos,
    1,
    c.data_lancamento,
    c.documento,
    c.historico,
    NULL,
    'Pagamento sem venda'
FROM creditos c
LEFT JOIN vendas v ON v.codigo = c.referencia_venda
WHERE v.codigo IS NULL

ORDER BY situacao, codigo_venda;
