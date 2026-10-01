"""
Gera dados FICTÍCIOS de exemplo para o projeto:
  - dados/entrada/vendas.xlsx         (exportação do sistema de vendas)
  - dados/entrada/extrato_bancario.csv (exportação do internet banking)

Os dados imitam exportações reais: valores no formato brasileiro ("1.234,56"),
datas dd/mm/aaaa, CSV separado por ";" em latin-1, e alguns erros de propósito
(pagamento faltando, valor diferente, pagamento duplicado, linha inválida...)
para que a conciliação tenha o que encontrar.

Uso:  python dados/gerar_dados.py
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook

random.seed(42)  # mesma semente = mesmos dados toda vez

PASTA = Path(__file__).parent / "entrada"
PASTA.mkdir(parents=True, exist_ok=True)

NOMES = [
    "Ana Souza", "Bruno Lima", "Carla Mendes", "Diego Alves", "Elisa Rocha",
    "Felipe Costa", "Gabriela Nunes", "Henrique Dias", "Isabela Freitas",
    "João Pereira", "Karina Lopes", "Lucas Martins", "Mariana Teixeira",
    "Nicolas Barros", "Olívia Cardoso", "Paulo Ribeiro", "Renata Gomes",
]
FORMAS = ["PIX", "PIX", "PIX", "TED", "Boleto"]
INICIO = date(2026, 9, 1)


def br(valor: float) -> str:
    """Formata 1234.5 como '1.234,50'."""
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def dt(d: date) -> str:
    return d.strftime("%d/%m/%Y")


# ---------------------------------------------------------------- vendas
vendas = []
for i in range(1, 61):
    vendas.append({
        "codigo": f"VND-{i:05d}",
        "data": INICIO + timedelta(days=random.randint(0, 25)),
        "cliente": random.choice(NOMES),
        "valor": round(random.uniform(80, 2500), 2),
        "forma": random.choice(FORMAS),
        "status": "Faturada",
    })

# cenários de problema (índices fixos para ficar fácil de conferir)
canceladas = {7, 22, 41}            # vendas canceladas
cancelada_paga = 22                 # cancelada, mas o cliente pagou mesmo assim
sem_pagamento = {3, 15, 28, 36, 52}  # cliente não pagou
divergentes = {9: -25.00, 18: +10.50, 33: -0.99, 47: -150.00}  # pagou valor diferente
duplicados = {12, 55}               # pagamento lançado duas vezes

for i in canceladas:
    vendas[i - 1]["status"] = "Cancelada"

# ---------------------------------------------------------------- extrato
lancamentos = []
for i, v in enumerate(vendas, start=1):
    if i in sem_pagamento or (i in canceladas and i != cancelada_paga):
        continue
    valor = round(v["valor"] + divergentes.get(i, 0), 2)
    tipo = "PIX RECEBIDO" if v["forma"] == "PIX" else (
        "TED RECEBIDA" if v["forma"] == "TED" else "LIQUIDACAO BOLETO")
    primeiro_nome = v["cliente"].split()[0].upper()
    data_pag = v["data"] + timedelta(days=random.randint(0, 3))
    lanc = {
        "data": data_pag,
        "historico": f"{tipo} - {v['codigo']} {primeiro_nome}",
        "documento": f"{random.randint(100000, 999999)}",
        "valor": valor,
    }
    lancamentos.append(lanc)
    if i in duplicados:
        lancamentos.append({**lanc, "documento": f"{random.randint(100000, 999999)}"})

# pagamentos que não correspondem a nenhuma venda
lancamentos += [
    {"data": date(2026, 9, 10), "historico": "PIX RECEBIDO - RENATA G", "documento": "481516", "valor": 349.90},
    {"data": date(2026, 9, 19), "historico": "TED RECEBIDA - VND-00099 PAULO", "documento": "234234", "valor": 1200.00},
    {"data": date(2026, 9, 24), "historico": "PIX RECEBIDO - MARCOS T", "documento": "778899", "valor": 89.90},
]
# débitos (tarifas e pagamentos) — devem ser ignorados na conciliação de recebimentos
lancamentos += [
    {"data": date(2026, 9, 5), "historico": "TARIFA PACOTE SERVICOS", "documento": "000001", "valor": -59.90},
    {"data": date(2026, 9, 15), "historico": "PAGTO FORNECEDOR XYZ", "documento": "000002", "valor": -1830.00},
]
lancamentos.sort(key=lambda x: x["data"])

# ---------------------------------------------------------------- grava vendas.xlsx
wb = Workbook()
ws = wb.active
ws.title = "Vendas"
ws.append(["Código", "Data", "Cliente", "Valor (R$)", "Forma de Pagamento", "Status"])
for v in vendas:
    ws.append([v["codigo"], dt(v["data"]), f"  {v['cliente']} ", br(v["valor"]), v["forma"], v["status"]])
# linhas com problema de dados (exportações reais sempre têm alguma)
ws.append(["VND-00061", "31/09/2026", "Teste Sistema", "150,00", "PIX", "Faturada"])  # data que não existe
ws.append(["VND-00062", "20/09/2026", "Lucas Martins", "", "PIX", "Faturada"])        # valor vazio
wb.save(PASTA / "vendas.xlsx")

# ---------------------------------------------------------------- grava extrato_bancario.csv
with open(PASTA / "extrato_bancario.csv", "w", newline="", encoding="latin-1") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["Data", "Histórico", "Documento", "Valor"])
    for l in lancamentos:
        w.writerow([dt(l["data"]), l["historico"], l["documento"], br(l["valor"])])
    w.writerow(["22/09/2026", "PIX RECEBIDO - VND-00030 HENRIQUE", "556677", "R$ abc"])  # valor ilegível

print(f"Gerados {len(vendas) + 2} registros de vendas e {len(lancamentos) + 1} lançamentos em {PASTA}")
