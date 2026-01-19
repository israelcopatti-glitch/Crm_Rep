import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="AM CRM", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>
    header, footer, #MainMenu, .stDeployButton {visibility: hidden; display: none !important;}
    [data-testid="stHeader"] {display: none !important;}
    .block-container {padding-top: 1rem !important;}
</style>""", unsafe_allow_html=True)

# --- 2. BANCO DE DADOS OTIMIZADO ---
def init_db():
    conn = sqlite3.connect("am_crm_perf_2026.db", check_same_thread=False)
    # Ativa modo de alta performance
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, 
        produto TEXT, qtde REAL, preco REAL, data TEXT, UNIQUE(cliente, sku, data, preco))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS jornal (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, produto TEXT, 
        preco_oferta REAL, validade TEXT, UNIQUE(sku, preco_oferta, validade))""")
    conn.commit()
    return conn

db = init_db()

# --- 3. LEITURA DE PDF (LEVE) ---
def extrair_pdf_rapido(file):
    lista = []
    cli, fon = "Cliente", ""
    try:
        with pdfplumber.open(file) as pdf:
            # Lê apenas o texto necessário para evitar consumo de RAM
            for page in pdf.pages:
                txt = page.extract_text()
                if not txt: continue
                
                # Captura cabeçalho apenas na primeira página
                if cli == "Cliente":
                    m_c = re.search(r"Nome Fantasia:\s*(.*)", txt)
                    if m_c: cli = m_c.group(1).split('\n')[0].strip()
                    m_f = re.search(r"Fone:\s*(\d+)", txt)
                    if m_f: fon = m_f.group(1).strip()
                
                for l in txt.split("\n"):
                    if re.match(r"^\d{4,7}\s+", l):
                        pts = l.split()
                        v = [x for x in pts if "," in x]
                        if len(v) >= 4:
                            try:
                                idx_f = pts.index(v[0])
                                lista.append((cli, fon, pts[0], " ".join(pts[1:idx_f]), 
                                              float(v[-3].replace(".", "").replace(",", ".")), 
                                              float(v[-2].replace(".", "").replace(",", ".")), 
                                              datetime.now().strftime("%Y-%m-%d")))
                            except: continue
    except: pass
    return lista, cli

# --- 4. INTERFACE ---
st.title("🚀 AM Representações")
t1, t2, t3, t4, t5 = st.tabs(["📥 Pedido", "📰 Jornal", "🔥 Cruzar", "📊 Histórico", "📋 Ofertas"])

with t1:
    if "pk" not in st.session_state: st.session_state.pk = 0
    f = st.file_uploader("Subir Pedido", type="pdf", key=f"p_{st.session_state.pk}")
    if f:
        dados, cliente_nome = extrair_pdf_rapido(f)
        if dados:
            st.success(f"✅ Pronto para salvar: {cliente_nome}")
            if st.button("💾 Salvar Histórico (Rápido)"):
                # Inserção em lote (MUITO mais rápido)
                db.executemany("INSERT OR
