import pytest

from conciliacao.extracao import data_br_para_iso, extrair_referencia, valor_br_para_centavos


@pytest.mark.parametrize("entrada, esperado", [
    ("1.234,56", 123456),
    ("R$ 89,90", 8990),
    ("-59,90", -5990),
    ("  0,99 ", 99),
    ("1.000.000,00", 100000000),
    (150.5, 15050),
    ("", None),
    ("R$ abc", None),
    (None, None),
])
def test_valor_br_para_centavos(entrada, esperado):
    assert valor_br_para_centavos(entrada) == esperado


@pytest.mark.parametrize("entrada, esperado", [
    ("05/09/2026", "2026-09-05"),
    (" 30/09/2026 ", "2026-09-30"),
    ("31/09/2026", None),   # setembro não tem dia 31
    ("2026-09-05", None),   # formato errado
    ("", None),
])
def test_data_br_para_iso(entrada, esperado):
    assert data_br_para_iso(entrada) == esperado


@pytest.mark.parametrize("historico, esperado", [
    ("PIX RECEBIDO - VND-00012 MARIA", "VND-00012"),
    ("ted recebida vnd-00450 joao", "VND-00450"),
    ("PIX RECEBIDO - RENATA G", None),
    ("TARIFA PACOTE SERVICOS", None),
    ("VND-123 incompleto", None),
])
def test_extrair_referencia(historico, esperado):
    assert extrair_referencia(historico) == esperado
