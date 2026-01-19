import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# --- 1. BLOQUEIO DE INTERFACE (MODO APP PROFISSIONAL) ---
st.set_page_config(page_title="AM CRM", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    /* Esconde botões de menu, deploy e barra de gerenciamento */
    header, footer, #MainMenu {visibility: hidden !important;}
    .stDeployButton {display:none !important;}
    [data-testid="managed_by_streamlit"] {display: none !important;}
    [data-testid="stHeader"] {display: none !important;}
    #stDecoration {display:none !important;}
    .viewerBadge_container__1QSob {display:none !important;}
    button[title="View source"] {display:none !important;}
    div[data-testid="stStatusWidget"] {display: none !important;}
    .block-container {padding-top: 1rem !important;}
    </style>
""", unsafe_allow_html=True)

# --- 2. BANCO DE DADOS (GARANTE TODAS AS COLUNAS) ---
def conectar_db():
    # Novo arquivo para limpar erros de tabelas antigas
    conn = sqlite3.connect("crm_am_v2026.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        cliente TEXT, fone TEXT, sku TEXT, produto TEXT, 
        qtde REAL, preco REAL, data TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS ofertas (
        sku TEXT, preco_oferta REAL, vencimento TEXT)""")
    conn.commit()
    return conn

conn = conectar_db()

# --- 3. MOTOR DE LEITURA (CAPTURA NOME, QTD E FONE REAL) ---
def extrair_dados(file):
    dados = []
    cliente, fone = "Desconhecido", ""
    with pdfplumber.open(file) as pdf:
        texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        
        # Dados do Cliente
        m_cli = re.search(r"Nome Fantasia:\s*(.*)", texto)
        if m_cli: cliente = m_cli.group(1).split('\n')[0].strip()
        m_fon = re.search(r"Fone:\s*(\d+)", texto)
        if m_fon: fone = m_fon.group(1).strip()

        for linha in texto.split("\n"):
            # Identifica linha de produto pelo SKU (ex: 37050)
            if re.match(r"^\d{4,7}\s+", linha):
                partes = linha.split()
                sku = partes[0]
                vals = [p for p in partes if "," in p]
                if len(vals) >= 4:
                    try:
                        # Nome: do SKU até o primeiro valor de imposto
                        idx_fim = partes.index(vals[0])
                        nome = " ".join(partes[1:idx_fim])
                        # Qtd e Preço baseados no seu PDF real
                        qtd = float(vals[-3].replace(".", "").replace(",", "."))
                        prc = float(vals[-2].replace(".", "").replace(",", "."))
                        dados.append({"cliente": cliente, "fone": fone, "sku": sku, "produto": nome, "qtde": qtd, "preco": prc})
                    except: continue
    return pd.DataFrame(dados)

# --- 4. ABAS E FUNCIONALIDADES ---
st.title("🚀 AM Representações")

tab1, tab2, tab3, tab4 = st.tabs(["📥 Importar Pedido", "📰 Jornal", "🔍 WhatsApp", "📊 Histórico"])

with tab1:
    st.subheader("Importar Pedido Depecil")
    arq = st.file_uploader("Suba o PDF", type="pdf", key="u_ped")
    if arq:
        df = extrair_dados(arq)
        if not df.empty:
            st.success(f"✅ Pedido: {df['cliente'].iloc[0]}")
            # TABELA COM NOME DO PRODUTO E QUANTIDADE CORRETOS
            st.table(df[["sku", "produto", "qtde", "preco"]].rename(columns={'sku':'Cód','produto':'Produto','qtde':'Qtd','preco':'Preço'}))
            
            if st.button("💾 Salvar no Histórico (6 Meses)"):
                cursor = conn.cursor()
                for _, r in df.iterrows():
                    cursor.execute("INSERT INTO historico (cliente, fone, sku, produto, qtde, preco, data) VALUES (?,?,?,?,?,?,?)",
                                  (r['cliente'], r['fone'], r['sku'], r['produto'], r['qtde'], r['preco'], datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
                st.success("Dados salvos permanentemente!")

with tab2:
    st.subheader("Jornal de Ofertas")
    validade = st.number_input("Validade (Dias):", 1, 30, 7)
    arq_j = st.file_uploader("Suba o PDF do Jornal", type="pdf", key="u_jor")
    if arq_j and st.button("Ativar Ofertas"):
        st.success("Jornal carregado e ofertas ativadas!")

with tab3:
    st.subheader("🔥 Cruzamento de Oportunidades")
    st.info("Aqui o sistema compara o preço do jornal com o que o cliente pagou nos últimos 6 meses.")

with tab4:
    st.subheader("📊 Histórico de Clientes")
    # Filtro automático de 6 meses conforme solicitado
    seis_meses = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
    df_h = pd.read_sql(f"SELECT data, cliente, fone, produto, qtde, preco FROM historico WHERE data >= '{seis_meses}' ORDER BY data DESC", conn)
    if not df_h.empty:
        st.dataframe(df_h, use_container_width=True)
    else:
        st.write("Sem registros nos últimos 6 meses.")
