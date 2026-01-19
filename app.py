import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
import urllib.parse
from datetime import datetime, timedelta

# --- 1. BLOQUEIO DE INTERFACE (MODO APLICATIVO) ---
st.set_page_config(page_title="AM CRM Profissional", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
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

# --- 2. BANCO DE DADOS (HISTÓRICO 6 MESES) ---
def conectar_db():
    conn = sqlite3.connect("crm_vendas_am_final.db", check_same_thread=False)
    c = conn.cursor()
    # Tabela de Histórico
    c.execute("""CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, 
        sku TEXT, produto TEXT, qtde REAL, preco REAL, data TEXT)""")
    # Tabela de Jornal
    c.execute("""CREATE TABLE IF NOT EXISTS jornal (
        sku TEXT, produto_jornal TEXT, preco_oferta REAL, vencimento TEXT)""")
    conn.commit()
    return conn

conn = conectar_db()

# --- 3. MOTORES DE LEITURA CALIBRADOS ---
def extrair_depecil(file):
    dados = []
    cliente, fone = "Desconhecido", ""
    with pdfplumber.open(file) as pdf:
        texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        cliente_m = re.search(r"Nome Fantasia:\s*(.*)", texto)
        if cliente_m: cliente = cliente_m.group(1).split('\n')[0].strip()
        fone_m = re.search(r"Fone:\s*(\d+)", texto)
        if fone_m: fone = fone_m.group(1).strip()

        for linha in texto.split("\n"):
            if re.match(r"^\d{4,7}\s+", linha):
                partes = linha.split()
                sku = partes[0]
                vals = [p for p in partes if "," in p]
                if len(vals) >= 4:
                    try:
                        v_unit = float(vals[-2].replace(".", "").replace(",", "."))
                        v_qtde = float(vals[-3].replace(".", "").replace(",", "."))
                        idx_fim = partes.index(vals[0])
                        nome = " ".join(partes[1:idx_fim])
                        dados.append({"cliente": cliente, "fone": fone, "sku": sku, "produto": nome, "qtde": v_qtde, "preco": v_unit})
                    except: continue
    return pd.DataFrame(dados)

# --- 4. INTERFACE POR ABAS (TODAS AS OPÇÕES RESTAURADAS) ---
st.title("🚀 AM Representações - CRM")

tab1, tab2, tab3, tab4 = st.tabs(["📥 Importar Pedido", "📰 Jornal de Ofertas", "🔍 Cruzamento", "📊 Histórico de 6 Meses"])

with tab1:
    st.subheader("Importar Pedido Depecil")
    arq = st.file_uploader("Suba o PDF do Pedido", type="pdf", key="u1")
    if arq:
        df = extrair_depecil(arq)
        if not df.empty:
            st.success(f"✅ Pedido: {df['cliente'].iloc[0]}")
            st.table(df[["sku", "produto", "qtde", "preco"]])
            if st.button("💾 Salvar no Histórico"):
                c = conn.cursor()
                for _, r in df.iterrows():
                    c.execute("INSERT INTO historico (cliente, fone, sku, produto, qtde, preco, data) VALUES (?,?,?,?,?,?,?)",
                              (r['cliente'], r['fone'], r
