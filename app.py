import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="AM CRM", layout="wide")
st.markdown("<style>header, footer, #MainMenu {visibility: hidden !important;}</style>", unsafe_allow_html=True)

DB_NAME = "am_v2026_superfast.db"

# --- 2. FUNÇÕES DE BANCO (CONEXÃO ÚNICA POR OPERAÇÃO) ---
def execute_batch(query, data_list):
    with sqlite3.connect(DB_NAME, timeout=30) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executemany(query, data_list)
        conn.commit()

def query_db(query):
    with sqlite3.connect(DB_NAME, timeout=30) as conn:
        return pd.read_sql(query, conn)

# Inicialização
with sqlite3.connect(DB_NAME) as conn:
    conn.execute("""CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, 
        produto TEXT, qtde REAL, preco REAL, data TEXT, lote TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS jornal (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, produto TEXT, 
        preco_oferta REAL, validade TEXT, lote TEXT)""")

# --- 3. MOTOR DE EXTRAÇÃO ---
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
            for l in txt.split("\n"):
                if re.match(r"^\d{4,7}\s+", l):
                    pts = l.split()
                    v = [x for x in pts if "," in x]
                    if len(v) >= 4:
                        try:
                            idx = pts.index(v[0])
                            lista.append((cli, fon, pts[0].strip(), " ".join(pts[1:idx]), 
                                          float(v[-3].replace(".", "").replace(",", ".")), 
                                          float(v[-2].replace(".", "").replace(",", ".")), 
                                          datetime.now().strftime("%Y-%m-%d"), file.name))
                        except: continue
    return lista, cli

# --- 4. INTERFACE ---
st.title("AM Representações")
t1, t2, t3, t4, t5 = st.tabs(["📥 Pedido", "📰 Jornal", "🔥 Cruzar", "📊 Histórico", "📋 Ofertas"])

with t1:
    f = st.file_uploader("Subir Pedido", type="pdf", key="up_p")
    if f:
        dados, cliente_nome = extrair_pdf(f)
        if dados:
            st.success(f"Lido: {cliente_nome}")
            if st.button("💾 SALVAR PEDIDO"):
                execute_batch("INSERT INTO historico (cliente, fone, sku, produto, qtde, preco, data, lote) VALUES (?,?,?,?,?,?,?,?)", dados)
                st.rerun()

with t2:
    st.subheader("Prazo do Jornal")
    if "d" not in st.session_state: st.session_state.d = 7
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("➖"): st.session_state.d = max(1, st.session_state.d - 1)
    with c2:
        st.markdown(f"<h2 style='text-align: center;'>{st.session_state.d} Dias</h2>", unsafe_allow_html=True)
    with c3:
        if st.button("➕"): st.session_state.d += 1

    dt_venc = (datetime.now() + timedelta(days=st.session_state.d)).strftime("%Y-%m-%d")
    fj = st.file_uploader("Subir Jornal", type="pdf", key="up_j")
    
    if fj and st.button("🚀 ATIVAR JORNAL"):
        with st.spinner("Gravando ofertas..."):
            dados_j, _ = extrair_pdf(fj)
            if dados_j:
                # Ajusta para o formato da tabela jornal: sku, produto, preco, validade, lote
                lista_j = [(d[2], d[3], d[5], dt_venc, fj.name) for d in dados_j]
                execute_batch("INSERT INTO jornal (sku, produto, preco_oferta, validade, lote) VALUES (?,?,?,?,?)", lista_j)
                st.success("Jornal ativado com sucesso!")
                st.rerun()

with t3:
    q = """SELECT h.cliente, h.fone, j.produto, h.preco as antigo, j.preco_oferta as novo, j.validade, j.lote
           FROM jornal j INNER JOIN historico h ON j.sku = h.sku 
           WHERE j.preco_oferta < h.preco GROUP BY h.cliente, j.sku"""
    df_c = query_db(q)
    if not df_c.empty:
        hoje = datetime.now().strftime("%Y-%m-%d")
        df_c['Status'] = df_c['validade'].apply(lambda x: "⚠️ VENCIDO" if x < hoje else "✅ OK")
        st.dataframe(df_c, use_container_width=True)
    else:
        st.warning("Nenhum cruzamento encontrado.")

with t4:
    clis = query_db("SELECT DISTINCT cliente FROM historico")
    if not clis.empty:
        sel = st.selectbox("Cliente:", ["Todos"] + clis['cliente'].tolist())
        sql = "SELECT id, cliente, produto, preco, data, lote FROM historico"
        if sel != "Todos": sql += f" WHERE cliente='{sel}'"
        st.dataframe(query_db(sql + " ORDER BY id DESC"), use_container_width=True)
        idx = st.number_input("ID p/ apagar:", min_value=0)
        if st.button("Apagar"):
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("DELETE FROM historico WHERE id=?", (idx,))
            st.rerun()

with t5:
    st.subheader("Gerenciar Jornais")
    lotes = query_db("SELECT lote, validade, COUNT(*) as itens FROM jornal GROUP BY lote")
    if not lotes.empty:
        st.table(lotes)
        excluir = st.selectbox("Escolha o arquivo para remover:", lotes['lote'].tolist())
        if st.button(f"🗑️ EXCLUIR ARQUIVO: {excluir}"):
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("DELETE FROM jornal WHERE lote=?", (excluir,))
            st.rerun()
