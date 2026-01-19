import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="AM CRM", layout="wide")
st.markdown("<style>header, footer, #MainMenu {visibility: hidden !important;}</style>", unsafe_allow_html=True)

DB_NAME = "am_crm_v2026_final.db"

# --- 2. BANCO DE DADOS (RÁPIDO) ---
def run_db(query, params=()):
    with sqlite3.connect(DB_NAME, timeout=30) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()

def query_db(query, params=()):
    with sqlite3.connect(DB_NAME, timeout=30) as conn:
        return pd.read_sql(query, conn, params=params)

# Inicialização
run_db("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, produto TEXT, preco REAL, data TEXT, lote TEXT)")
run_db("CREATE TABLE IF NOT EXISTS jornal (id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, produto TEXT, preco_oferta REAL, validade TEXT, lote TEXT)")

# --- 3. MOTOR DE EXTRAÇÃO (OTIMIZADO) ---
def extrair_pdf(file):
    lista = []
    cli, fon = "Cliente", ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            txt = page.extract_text()
            if not txt: continue
            if cli == "Cliente":
                m_c = re.search(r"Nome Fantasia:\s*(.*)", txt)
                if m_c: cli = m_c.group(1).split('\n')[0].strip()
                m_f = re.search(r"Fone:\s*(\d+)", txt)
                if m_f: fon = m_f.group(1).strip()
            for linha in txt.split('\n'):
                sku_m = re.search(r"\b(\d{4,7})\b", linha)
                if sku_m:
                    sku = sku_m.group(1)
                    precos = re.findall(r"(\d{1,3}(?:\.\d{3})*,\d{2})", linha)
                    if precos:
                        valor = float(precos[-1].replace('.', '').replace(',', '.'))
                        lista.append((cli, fon, sku, linha[:40].strip(), valor))
    return lista

# --- 4. INTERFACE ---
st.title("AM Representações")
t1, t2, t3, t4, t5 = st.tabs(["📥 Pedido", "📰 Jornal", "🔥 Cruzar", "📊 Histórico", "📋 Ofertas"])

with t1:
    f_p = st.file_uploader("Subir Pedido", type="pdf", key="p")
    if f_p:
        # Verifica se já existe esse lote no histórico
        existe = query_db("SELECT COUNT(*) as total FROM historico WHERE lote = ?", (f_p.name,))['total'][0]
        if existe > 0:
            st.warning(f"⚠️ Atenção: O arquivo '{f_p.name}' já foi importado anteriormente.")
        
        dados = extrair_pdf(f_p)
        if dados:
            st.info(f"Cliente: {dados[0][0]}")
            if st.button("💾 SALVAR PEDIDO (MESMO SE DUPLICADO)"):
                hoje = datetime.now().strftime("%Y-%m-%d")
                with sqlite3.connect(DB_NAME) as conn:
                    for d in dados:
                        conn.execute("INSERT INTO historico (cliente, fone, sku, produto, preco, data, lote) VALUES (?,?,?,?,?,?,?)",
                                   (d[0], d[1], d[2], d[3], d[4], hoje, f_p.name))
                st.success("Pedido registrado!")
                st.rerun()

with t2:
    # Seletor - Dias +
    if "d" not in st.session_state: st.session_state.d = 7
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("➖ 1 Dia"): st.session_state.d = max(1, st.session_state.d - 1)
    with c2:
        st.markdown(f"<h2 style='text-align: center;'>{st.session_state.d} Dias</h2>", unsafe_allow_html=True)
    with c3:
        if st.button("➕ 1 Dia"): st.session_state.d += 1
    
    dt_v = (datetime.now() + timedelta(days=st.session_state.d)).strftime("%Y-%m-%d")
    f_j = st.file_uploader("Subir Jornal", type="pdf", key="j")
    
    if f_j:
        existe_j = query_db("SELECT COUNT(*) as total FROM jornal WHERE lote = ?", (f_j.name,))['total'][0]
        if existe_j > 0:
            st.warning(f"⚠️ Este Jornal ({f_j.name}) já está ativo.")
            
        if st.button("🚀 ATIVAR JORNAL"):
            dados_j = extrair_pdf(f_j)
            if dados_j:
                with sqlite3.connect(DB_NAME) as conn:
                    for d in dados_j:
                        conn.execute("INSERT INTO jornal (sku, produto, preco_oferta, validade, lote) VALUES (?,?,?,?,?)",
                                   (d[2], d[3], d[4], dt_v, f_j.name))
                st.success("Jornal ativado!")
                st.rerun()

with t3:
    # Cruzamento de dados com número real do cliente
    df_c = query_db("""SELECT h.cliente, h.fone, j.produto, h.preco as antigo, j.preco_oferta as novo, j.validade, j.lote
                       FROM jornal j INNER JOIN historico h ON j.sku = h.sku 
                       WHERE j.preco_oferta < h.preco GROUP BY h.cliente, j.sku""")
    if not df_c.empty:
        st.dataframe(df_c, use_container_width=True)
    else:
        st.info("Sem ofertas vantajosas no momento.")

with t5:
    st.subheader("Gerenciar Jornais")
    lotes = query_db("SELECT lote, validade, COUNT(*) as itens FROM jornal GROUP BY lote")
    if not lotes.empty:
        st.table(lotes)
        l_del = st.selectbox("Remover Arquivo:", lotes['lote'].tolist())
        if st.button("🗑️ EXCLUIR"):
            run_db("DELETE FROM jornal WHERE lote=?", (l_del,))
            st.rerun()
