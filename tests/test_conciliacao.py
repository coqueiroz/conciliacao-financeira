"""Testa as regras de conciliação (sql/conciliacao.sql) com um banco em memória."""
import pandas as pd
import pytest

from conciliacao import banco


def venda(codigo, valor, status="Faturada", data="2026-09-10"):
    return {"codigo": codigo, "data_venda": data, "cliente": "Cliente Teste",
            "valor_centavos": valor, "forma_pagamento": "PIX", "status": status}


def credito(referencia, valor, historico=None, data="2026-09-12"):
    return {"data_lancamento": data, "historico": historico or f"PIX RECEBIDO - {referencia}",
            "documento": "123", "valor_centavos": valor, "referencia_venda": referencia}


@pytest.fixture
def resultado():
    vendas = pd.DataFrame([
        venda("VND-00001", 10000),                       # pago certinho
        venda("VND-00002", 10000),                       # pago a menos
        venda("VND-00003", 10000),                       # pago duas vezes
        venda("VND-00004", 10000, data="2026-09-01"),    # não pago
        venda("VND-00005", 10000, status="Cancelada"),   # cancelada e não paga -> ignorar
        venda("VND-00006", 10000, status="Cancelada"),   # cancelada mas paga -> alertar
        venda("VND-00007", 10000),                       # pago com 1 centavo a menos
    ])
    lancamentos = pd.DataFrame([
        credito("VND-00001", 10000),
        credito("VND-00002", 9000),
        credito("VND-00003", 10000),
        credito("VND-00003", 10000),
        credito("VND-00006", 10000),
        credito("VND-00007", 9999),
        credito(None, 5000, historico="PIX RECEBIDO - SEM REFERENCIA"),
        credito("VND-99999", 7000),                      # código que não existe
        credito(None, -2000, historico="TARIFA"),        # débito -> ignorar
    ])
    conn = banco.conectar()
    banco.criar_tabelas(conn)
    banco.carregar(conn, vendas, lancamentos)
    return banco.conciliar(conn, data_referencia="2026-09-30", tolerancia_centavos=0)


def situacao(resultado, codigo):
    return resultado.loc[resultado["codigo_venda"] == codigo, "situacao"].tolist()


def test_venda_paga_corretamente(resultado):
    assert situacao(resultado, "VND-00001") == ["Conciliado"]


def test_valor_divergente(resultado):
    linha = resultado[resultado["codigo_venda"] == "VND-00002"].iloc[0]
    assert linha["situacao"] == "Valor divergente"
    assert linha["diferenca"] == pytest.approx(-10.00)


def test_pagamento_duplicado(resultado):
    assert situacao(resultado, "VND-00003") == ["Pagamento duplicado"]


def test_venda_sem_pagamento_conta_dias_em_aberto(resultado):
    linha = resultado[resultado["codigo_venda"] == "VND-00004"].iloc[0]
    assert linha["situacao"] == "Venda sem pagamento"
    assert linha["dias_em_aberto"] == 29


def test_cancelada_sem_pagamento_fica_fora(resultado):
    assert situacao(resultado, "VND-00005") == []


def test_cancelada_com_pagamento_gera_alerta(resultado):
    assert situacao(resultado, "VND-00006") == ["Venda cancelada com pagamento"]


def test_pagamentos_sem_venda(resultado):
    sem_venda = resultado[resultado["situacao"] == "Pagamento sem venda"]
    assert len(sem_venda) == 2
    assert set(sem_venda["valor_pago"]) == {50.00, 70.00}


def test_debitos_sao_ignorados(resultado):
    assert (resultado["valor_pago"].dropna() > 0).all()


def test_tolerancia_aceita_diferenca_de_centavos():
    vendas = pd.DataFrame([venda("VND-00007", 10000)])
    lancamentos = pd.DataFrame([credito("VND-00007", 9999)])
    conn = banco.conectar()
    banco.criar_tabelas(conn)
    banco.carregar(conn, vendas, lancamentos)
    sem_tolerancia = banco.conciliar(conn, "2026-09-30", tolerancia_centavos=0)
    com_tolerancia = banco.conciliar(conn, "2026-09-30", tolerancia_centavos=1)
    assert sem_tolerancia["situacao"].iloc[0] == "Valor divergente"
    assert com_tolerancia["situacao"].iloc[0] == "Conciliado"
