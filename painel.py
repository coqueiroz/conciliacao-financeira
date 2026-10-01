"""
Painel visual da conciliação (Streamlit).

Uso local:   streamlit run painel.py
Na internet: publicado pelo Streamlit Community Cloud a partir do GitHub.

Tem dois modos, escolhidos pela configuração MODO (Secrets do Streamlit ou variável de ambiente):
  - "demonstracao" (padrão): para portfólio; abre com dados de exemplo de uma loja fictícia.
  - "cliente": para uso real; não mostra exemplos e abre pedindo os arquivos do cliente.
Os indicadores e as barras do gráfico são clicáveis e filtram a tabela de detalhes.
"""
from __future__ import annotations

import logging
import os
import re
import io
import tempfile
from datetime import date
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from conciliacao import notificacao, pipeline, relatorio
from conciliacao.relatorio import COLUNAS, ORDEM_SITUACOES

RAIZ = Path(__file__).resolve().parent
EXEMPLO_VENDAS = RAIZ / "dados/entrada/vendas.xlsx"
EXEMPLO_EXTRATO = RAIZ / "dados/entrada/extrato_bancario.csv"
AZUL, AZUL_CLARO = "#2a78d6", "#a9c8ef"

TODAS_PENDENCIAS = "Todas as pendências"
INVALIDAS = "Linhas inválidas"
COLUNAS_MOEDA = ("Valor da venda (R$)", "Valor recebido (R$)", "Diferença (R$)")
COLUNAS_DATA = ("Data da venda", "Data do pagamento")

logging.basicConfig(level=logging.WARNING)
st.set_page_config(page_title="Conciliação Financeira", page_icon="📊", layout="wide")


def moeda(valor: float) -> str:
    texto = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-R$ {texto}" if valor < 0 else f"R$ {texto}"


@st.cache_data(show_spinner="Conciliando...")
def conciliar(vendas_bytes: bytes, extrato_bytes: bytes, data_ref: str, tolerancia: float):
    """Grava os arquivos recebidos numa pasta temporária e roda a conciliação."""
    with tempfile.TemporaryDirectory() as pasta:
        vendas = Path(pasta) / "vendas.xlsx"
        extrato = Path(pasta) / "extrato_bancario.csv"
        vendas.write_bytes(vendas_bytes)
        extrato.write_bytes(extrato_bytes)
        resultado, invalidos = pipeline.executar(vendas, extrato, data_ref, tolerancia)
        excel = Path(pasta) / "relatorio.xlsx"
        relatorio.gerar_excel(resultado, invalidos, excel, data_ref)
        return resultado, invalidos, excel.read_bytes()


def filtrar(valor: str) -> None:
    """Chamado pelos botões dos indicadores: muda o filtro da tabela de detalhes."""
    st.session_state["filtro"] = valor


def configuracao(chave: str, padrao: str = "") -> str:
    """Lê uma configuração do Secrets do Streamlit ou, se não houver, das variáveis de ambiente."""
    try:
        if chave in st.secrets:
            return str(st.secrets[chave])
    except Exception:  # sem arquivo de secrets
        pass
    return os.environ.get(chave, padrao)


MODO = configuracao("MODO", "demonstracao").strip().lower()
MODO_CLIENTE = MODO == "cliente"
NOME_CLIENTE = configuracao("NOME_CLIENTE")


@st.cache_data
def modelo_vendas() -> bytes:
    """Planilha modelo, com as colunas que o sistema espera."""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Vendas"
    ws.append(["Código", "Data", "Cliente", "Valor (R$)", "Forma de Pagamento", "Status"])
    ws.append(["VND-00001", "05/09/2026", "Maria Silva", "1.250,90", "PIX", "Faturada"])
    ws.append(["VND-00002", "06/09/2026", "João Souza", "389,00", "Boleto", "Cancelada"])
    for coluna, largura in zip("ABCDEF", (12, 12, 22, 12, 20, 12)):
        ws.column_dimensions[coluna].width = largura
    saida = io.BytesIO()
    wb.save(saida)
    return saida.getvalue()


def modelo_extrato() -> bytes:
    linhas = ["Data;Histórico;Documento;Valor",
              "05/09/2026;PIX RECEBIDO - VND-00001 MARIA;123456;1.250,90",
              "06/09/2026;TARIFA BANCARIA;000001;-19,90"]
    return ("\n".join(linhas) + "\n").encode("latin-1")


# ------------------------------------------------------------------ parâmetros (barra lateral)
with st.sidebar:
    if not MODO_CLIENTE:
        st.header("Dados")
        origem = st.radio("Origem", ["Usar dados de exemplo", "Enviar meus arquivos"], label_visibility="collapsed")
    st.header("Ajustes")
    data_ref = st.date_input("Data de referência",
                             value=date.today() if MODO_CLIENTE else date(2026, 9, 30), format="DD/MM/YYYY",
                             help="Usada para calcular há quantos dias cada venda está sem pagamento.")
    tolerancia = st.number_input("Tolerância (R$)", min_value=0.0, step=0.05, value=0.0,
                                 help="Diferenças até esse valor contam como conciliadas.")

titulo = f"Conciliação financeira · {NOME_CLIENTE}" if NOME_CLIENTE else "Conciliação financeira"
titulo_exibido = False

# ------------------------------------------------------------------ envio dos arquivos
if MODO_CLIENTE or origem == "Enviar meus arquivos":
    enviados = bool(st.session_state.get("up_vendas")) and bool(st.session_state.get("up_extrato"))
    st.title(titulo)
    titulo_exibido = True
    if not enviados:
        st.write("Confira em poucos segundos se todas as suas vendas foram pagas. "
                 "É só enviar os dois arquivos abaixo.")
    with st.expander("Arquivos enviados ✓" if enviados else "Envie seus arquivos", expanded=not enviados):
        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.markdown("**1. Planilha de vendas** (Excel)")
            arq_vendas = st.file_uploader("Planilha de vendas", type="xlsx", key="up_vendas",
                                          label_visibility="collapsed")
            st.download_button("Baixar modelo da planilha", modelo_vendas(), "modelo_vendas.xlsx",
                               key="modelo_v")
        with c2:
            st.markdown("**2. Extrato do banco** (CSV)")
            arq_extrato = st.file_uploader("Extrato do banco", type="csv", key="up_extrato",
                                           label_visibility="collapsed")
            st.download_button("Baixar modelo do extrato", modelo_extrato(), "modelo_extrato.csv",
                               key="modelo_e")
        st.caption("Os arquivos são usados só durante a análise e não ficam guardados. "
                   "No extrato, o código da venda (ex.: VND-00001) precisa aparecer no histórico do pagamento.")
    if not (arq_vendas and arq_extrato):
        st.stop()
    vendas_bytes, extrato_bytes = arq_vendas.getvalue(), arq_extrato.getvalue()
else:
    if not EXEMPLO_VENDAS.exists():
        st.error("Dados de exemplo não encontrados. Rode antes: `python dados/gerar_dados.py`")
        st.stop()
    vendas_bytes, extrato_bytes = EXEMPLO_VENDAS.read_bytes(), EXEMPLO_EXTRATO.read_bytes()

try:
    resultado, invalidos, excel_bytes = conciliar(vendas_bytes, extrato_bytes, data_ref.isoformat(), tolerancia)
except Exception:
    logging.exception("Falha ao ler os arquivos")
    st.error("Não consegui ler os arquivos. Confira se eles seguem os modelos (as mesmas colunas, "
             "com os mesmos nomes) e tente de novo.")
    st.stop()

ind = pipeline.indicadores(resultado)
contagem = resultado["situacao"].value_counts().reindex(ORDEM_SITUACOES, fill_value=0)

st.session_state.setdefault("filtro", TODAS_PENDENCIAS)

# ------------------------------------------------------------------ cabeçalho e indicadores
if not titulo_exibido:
    st.title(titulo)
if not MODO_CLIENTE and origem == "Usar dados de exemplo":
    st.info("Demonstração com dados de uma loja fictícia. Para testar com os seus arquivos, "
            "escolha **Enviar meus arquivos** na barra lateral.", icon="ℹ️")
st.caption(f"Vendas x extrato bancário · referência {data_ref:%d/%m/%Y} · clique nos cartões ou nas barras para ver os detalhes")

CSS_CARTOES = """
<style>
/* cada indicador é um cartão; um botão invisível cobre o cartão inteiro e recebe o clique */
div[class*="st-key-cartao_"] {
    position: relative;
    border: 1px solid rgba(128, 128, 128, 0.25);
    border-radius: 12px;
    padding: 14px 18px 10px;
    min-height: 140px;
    transition: border-color .15s, background-color .15s, transform .15s;
}
div[class*="st-key-cartao_"]:hover {
    border-color: #2a78d6;
    background-color: rgba(42, 120, 214, 0.06);
    transform: translateY(-1px);
}
div[class*="st-key-botao_"] {
    position: absolute !important; inset: 0; z-index: 2; margin: 0;
}
div[class*="st-key-botao_"] .stButton, div[class*="st-key-botao_"] button {
    width: 100% !important; height: 100% !important;
}
div[class*="st-key-botao_"] button { opacity: 0; cursor: pointer; }
div[class*="st-key-cartao_"] > div:not([class*="st-key-botao_"]) { pointer-events: none; }
div[class*="st-key-botao_"] button:disabled { cursor: default; }
div[class*="st-key-cartao_"] [data-testid="stMetricValue"] { font-size: 1.9rem; }
/*DESTAQUE*/
</style>
"""


def cartao(coluna, chave: str, titulo: str, valor, filtro_alvo: str, dica: str = "", desativado: bool = False):
    """Indicador clicável: clicar no cartão filtra a tabela de detalhes."""
    with coluna:
        with st.container(key=f"cartao_{chave}"):
            st.metric(titulo, valor)
            st.caption(dica if not desativado else "nada para mostrar")
            st.button(titulo, key=f"botao_{chave}", on_click=filtrar, args=(filtro_alvo,),
                      disabled=desativado, width="stretch")


CARTOES = {
    "conciliadas": "Conciliado",
    "pendencias": TODAS_PENDENCIAS,
    "aberto": "Venda sem pagamento",
    "invalidas": INVALIDAS,
}
ativo = next((k for k, alvo in CARTOES.items() if alvo == st.session_state["filtro"]), None)
destaque = (f'div.st-key-cartao_{ativo} {{ border-color: #2a78d6; box-shadow: 0 0 0 1px #2a78d6; '
            f'background-color: rgba(42, 120, 214, 0.08); }}') if ativo else ""
st.markdown(CSS_CARTOES.replace("/*DESTAQUE*/", destaque), unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
cartao(c1, "conciliadas", "Conciliadas", f"{ind['percentual_conciliado']:.0%}", "Conciliado",
       f"{ind['vendas_conciliadas']} de {ind['vendas_faturadas']} vendas")
cartao(c2, "pendencias", "Pendências", ind["pendencias"], TODAS_PENDENCIAS, "para analisar")
cartao(c3, "aberto", "Em aberto", moeda(ind["valor_em_aberto"]), "Venda sem pagamento",
       f"{contagem['Venda sem pagamento']} venda(s)")
cartao(c4, "invalidas", "Linhas inválidas", len(invalidos), INVALIDAS, "nos arquivos",
       desativado=invalidos.empty)

# ------------------------------------------------------------------ gráfico (barras clicáveis)
dados_grafico = contagem.rename_axis("Situação").reset_index(name="Quantidade")
dados_grafico["Diferença"] = [moeda(resultado.loc[resultado["situacao"] == s, "diferenca"].sum())
                              for s in dados_grafico["Situação"]]

clique = alt.selection_point(name="barra", fields=["Situação"], on="click")
barras = (
    alt.Chart(dados_grafico)
    .mark_bar(cornerRadiusEnd=4, height=22, cursor="pointer")
    .encode(
        x=alt.X("Quantidade:Q", title="Quantidade de casos", axis=alt.Axis(tickMinStep=1, tickCount=6)),
        y=alt.Y("Situação:N", sort=ORDEM_SITUACOES, title=None, axis=alt.Axis(labelLimit=260)),
        color=alt.condition(clique, alt.value(AZUL), alt.value(AZUL_CLARO)),
        tooltip=["Situação", "Quantidade", "Diferença"],
    )
    .add_params(clique)
)
rotulos = (alt.Chart(dados_grafico).mark_text(align="left", dx=6, color="gray")
           .encode(x="Quantidade:Q", y=alt.Y("Situação:N", sort=ORDEM_SITUACOES), text="Quantidade:Q"))

st.subheader("Casos por situação")
evento = st.altair_chart((barras + rotulos).properties(height=260), width="stretch",
                         on_select="rerun", selection_mode="barra", key="grafico")

# um clique novo numa barra muda o filtro (cliques antigos não sobrescrevem os botões)
selecionadas = evento.selection.get("barra", []) if evento else []
situacao_clicada = selecionadas[0]["Situação"] if selecionadas else None
if situacao_clicada and situacao_clicada != st.session_state.get("ultimo_clique"):
    st.session_state["filtro"] = situacao_clicada
st.session_state["ultimo_clique"] = situacao_clicada

# ------------------------------------------------------------------ detalhes
st.subheader("Detalhes")
opcoes = [TODAS_PENDENCIAS] + [s for s in ORDEM_SITUACOES if s != "Conciliado" and contagem[s] > 0]
opcoes += ["Conciliado"] + ([INVALIDAS] if not invalidos.empty else [])
if st.session_state["filtro"] not in opcoes:
    st.session_state["filtro"] = TODAS_PENDENCIAS


def rotulo(opcao: str) -> str:
    if opcao == TODAS_PENDENCIAS:
        return f"{opcao} ({ind['pendencias']})"
    if opcao == INVALIDAS:
        return f"{opcao} ({len(invalidos)})"
    return f"{opcao} ({contagem[opcao]})"


filtro = st.segmented_control("Mostrar", opcoes, format_func=rotulo, key="filtro",
                              selection_mode="single", label_visibility="collapsed")
filtro = filtro or TODAS_PENDENCIAS

if filtro == INVALIDAS:
    st.dataframe(invalidos[["origem", "linha_arquivo", "motivo"]].rename(
        columns={"origem": "Arquivo", "linha_arquivo": "Linha", "motivo": "Problema"}),
        hide_index=True, width="stretch")
else:
    if filtro == TODAS_PENDENCIAS:
        detalhe = resultado[resultado["situacao"] != "Conciliado"]
    else:
        detalhe = resultado[resultado["situacao"] == filtro]

    busca = st.text_input("Buscar por cliente, código ou documento", placeholder="Ex.: Elisa, VND-00028, 481516")
    if busca:
        termo = busca.strip().lower()
        texto = (detalhe[["cliente", "codigo_venda", "documentos", "historico"]]
                 .fillna("").astype(str).agg(" ".join, axis=1).str.lower())
        detalhe = detalhe[texto.str.contains(termo, regex=False)]

    if filtro == "Venda sem pagamento":
        detalhe = detalhe.sort_values("dias_em_aberto", ascending=False)

    colunas = [c for c in COLUNAS if c in detalhe and detalhe[c].notna().any()]
    tabela = detalhe[colunas].rename(columns=COLUNAS)
    if filtro == TODAS_PENDENCIAS:
        tabela.insert(0, "Situação", detalhe["situacao"].values)

    # formata para exibição (R$ 1.234,56 e dd/mm/aaaa) e deixa vazio o que não se aplica
    exibicao = tabela.copy()
    for c in exibicao.columns:
        if c in COLUNAS_MOEDA:
            exibicao[c] = tabela[c].map(lambda v: "" if pd.isna(v) else moeda(v))
        elif c in COLUNAS_DATA:
            exibicao[c] = tabela[c].map(lambda v: "" if pd.isna(v) else f"{v:%d/%m/%Y}")
        elif c in ("Qtd. pagamentos", "Dias em aberto"):
            exibicao[c] = tabela[c].map(lambda v: "" if pd.isna(v) else f"{int(v)}")
        else:
            exibicao[c] = tabela[c].fillna("")

    if tabela.empty:
        st.info("Nada encontrado com esse filtro.")
    else:
        st.dataframe(exibicao, hide_index=True, width="stretch")
        total = detalhe["diferenca"].sum()
        st.caption(f"{len(tabela)} registro(s) · diferença total: {moeda(total)}")
        st.download_button("Baixar esta lista (CSV)",
                           tabela.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                           file_name=f"{filtro.lower().replace(' ', '_')}.csv", mime="text/csv")

# ------------------------------------------------------------------ exportar e enviar
LIMITE_ENVIOS = 3  # por sessão, para evitar abuso do remetente na versão pública
EMAIL_VALIDO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def configurar_remetente() -> bool:
    """O remetente é configurado UMA vez por quem publica o sistema (Secrets do Streamlit ou .env).

    O usuário do painel nunca vê nem digita senha: só informa para quem enviar.
    """
    notificacao.carregar_env(RAIZ / ".env")
    try:
        for chave in ("GMAIL_USUARIO", "GMAIL_SENHA_APP"):
            if chave in st.secrets:
                os.environ.setdefault(chave, st.secrets[chave])
    except Exception:  # sem arquivo de secrets: tudo bem, usa só o .env
        pass
    return bool(os.environ.get("GMAIL_USUARIO") and os.environ.get("GMAIL_SENHA_APP"))


st.divider()
col_excel, col_email = st.columns([1, 2], gap="large")

with col_excel:
    st.subheader("Relatório")
    st.write("Planilha com o resumo e uma aba para cada pendência.")
    st.download_button("Baixar relatório completo (Excel)", excel_bytes,
                       file_name=f"conciliacao_{data_ref.isoformat()}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       type="primary")

with col_email:
    st.subheader("Enviar por e-mail")
    if not configurar_remetente():
        st.info("O envio de e-mail ainda não foi configurado neste servidor. "
                "Quem publica o sistema faz isso uma única vez (veja o README).")
    else:
        st.session_state.setdefault("envios", 0)
        with st.form("form_email", clear_on_submit=False, border=False):
            destinos = st.text_input("Para quem enviar", placeholder="financeiro@empresa.com, dono@empresa.com",
                                     help="Separe vários e-mails com vírgula.")
            enviar = st.form_submit_button("Enviar resumo e relatório",
                                           disabled=st.session_state["envios"] >= LIMITE_ENVIOS)
        st.caption("O e-mail leva o resumo da conciliação no corpo da mensagem e o Excel em anexo.")

        if enviar:
            lista = [e.strip() for e in destinos.replace(";", ",").split(",") if e.strip()]
            invalidos_email = [e for e in lista if not EMAIL_VALIDO.match(e)]
            if not lista:
                st.warning("Digite pelo menos um e-mail.")
            elif invalidos_email:
                st.warning(f"Confira estes endereços: {', '.join(invalidos_email)}")
            elif len(lista) > 5:
                st.warning("Envie para no máximo 5 endereços por vez.")
            else:
                with tempfile.TemporaryDirectory() as pasta:
                    anexo = Path(pasta) / f"conciliacao_{data_ref.isoformat()}.xlsx"
                    anexo.write_bytes(excel_bytes)
                    html = notificacao.montar_html(resultado, invalidos, data_ref.isoformat())
                    assunto = (f"Conciliação {data_ref:%d/%m/%Y}: {ind['pendencias']} pendência(s), "
                               f"{ind['percentual_conciliado']:.0%} conciliado")
                    try:
                        with st.spinner("Enviando..."):
                            notificacao.enviar_email(html, anexo, assunto, lista)
                        st.session_state["envios"] += 1
                        st.success(f"E-mail enviado para {', '.join(lista)}.")
                    except Exception:
                        logging.exception("Falha no envio")
                        st.error("Não foi possível enviar agora. Tente novamente em alguns minutos.")
        if st.session_state["envios"] >= LIMITE_ENVIOS:
            st.caption(f"Limite de {LIMITE_ENVIOS} envios por sessão atingido.")
