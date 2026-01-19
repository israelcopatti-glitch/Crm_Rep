import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO E BLOQUEIO ---
st.set_page_config(page_title="AM CRM", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>
    header, footer, #MainMenu, .stDeployButton {visibility: hidden; display: none !important;}
    [data-testid="stHeader"] {display: none !important;}
    .block-container {padding-top: 1rem !important;}
</style>""", unsafe_allow_html=True)

# --- 2. BANCO DE DADOS (Conexão Direta para evitar erros) ---
conn = sqlite3.connect("am_crm_v2026.db", check_same_thread=False)
conn.execute("""CREATE TABLE IF NOT EXISTS historico (
    id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, 
    produto TEXT, qtde REAL, preco REAL, data TEXT, UNIQUE(cliente, sku, data, preco))""")
conn.execute("""CREATE TABLE IF NOT EXISTS jornal (
    id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, produto TEXT, 
    preco_oferta REAL, validade TEXT, UNIQUE(sku, preco_oferta, validade))""")

# --- 3. MOTOR DE LEITURA (CALIBRADO) ---
def extrair_pdf(file):
    lista = []
    cli, fon = "Cliente", ""
    with pdfplumber.open(file) as pdf:
        txt = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        m_c = re.search(r"Nome Fantasia:\s*(.*)", txt)
        if m_c: cli = m_c.group(1).split('\n')[0].strip()
        m_f = re.search(r"Fone:\s*(\d+)", txt)
        if m_f: fon = m_f.group(1).strip()
        for l in txt.split("\n"):
            if re.match(r"^\d{4,7}\s+", l):
                p = l.split()
                v = [x for x in p if "," in x]
                if len(v) >= 4:
                    try:
                        idx_f = p.index(v[0])
                        lista.append({"cliente": cli, "fone": fon, "sku": p[0], "produto": " ".join(p[1:idx_f]), 
                                      "qtde": float(v[-3].replace(".", "").replace(",", ".")), 
                                      "preco": float(v[-2].replace(".", "").replace(",", "."))})
                    except: continue
    return pd.DataFrame(lista)

# --- 4. INTERFACE ---
st.title("AM Representações")
t1, t2, t3, t4, t5 = st.tabs(["📥 Pedido", "📰 Jornal", "🔥 Cruzar", "📊 Histórico", "📋 Ofertas"])

with t1:
    if "p_key" not in st.session_state: st.session_state.p_key = 0
    f = st.file_uploader("Subir Pedido", type="pdf", key=f"p_{st.session_state.p_key}")
    if f:
        df = extrair_pdf(f)
        if not df.empty:
            st.table(df[["sku", "produto", "qtde", "preco"]])
            if st.button("💾 Salvar Pedido"):
                for _, r in df.iterrows():
                    try: conn.execute("INSERT INTO historico (cliente, fone, sku, produto, qtde, preco, data) VALUES (?,?,?,?,?,?,?)",
                                     (r['cliente'], r['fone'], r['sku'], r['produto'], r['qtde'], r['preco'], datetime.now().strftime("%Y-%m-%d")))
                    except: pass
                conn.commit()
                st.session_state.p_key += 1
                st.rerun()

with t2:
    if "j_key" not in st.session_state: st.session_state.j_key = 0
    dt = st.date_input("Validade:", datetime.now() + timedelta(days=7))
    fj = st.file_uploader("Subir Jornal", type="pdf", key=f"j_{st.session_state.j_key}")
    if fj and st.button("Ativar Ofertas"):
        dfj = extrair_pdf(fj)
        if not dfj.empty:
            for _, r in dfj.iterrows():
                try: conn.execute("INSERT INTO jornal (sku, produto, preco_oferta, validade) VALUES (?,?,?,?)",
                                 (r['sku'], r['produto'], r['preco'], dt.strftime("%Y-%m-%d")))
                except: pass
            conn.commit()
            st.session_state.j_key += 1
            st.rerun()

with t3:
    conn.execute("DELETE FROM jornal WHERE validade < DATE('now')")
    h = pd.read_sql("SELECT * FROM historico", conn)
    o = pd.read_sql("SELECT * FROM jornal", conn)
    if not o.empty and not h.empty:
        c = pd.merge(o, h, on="sku", suffixes=('_j', '_h'))
        opt = c[c['preco_oferta'] < c['preco']].drop_duplicates(subset=['cliente', 'sku'])
        st.dataframe(opt[['cliente', 'produto_j', 'preco', 'preco_oferta', 'validade']])

with t4:
    clis = pd.read_sql("SELECT DISTINCT cliente FROM historico", conn)
    if not clis.empty:
        s = st.selectbox("Cliente:", ["Todos"] + clis['cliente'].tolist())
        q = "SELECT * FROM historico" + (f" WHERE cliente='{s}'" if s!="Todos" else "") + " ORDER BY id DESC"
        st.dataframe(pd.read_sql(q, conn))
        idx = st.number_input("ID para apagar:", min_value=0, step=1)
        if st.button("Excluir Item"):
            conn.execute(f"DELETE FROM historico WHERE id={idx}"); conn.commit(); st.rerun()

with t5:
    st.dataframe(pd.read_sql("SELECT * FROM jornal ORDER BY validade ASC", conn))
    idxj = st.number_input("ID oferta para apagar:", min_value=0, step=1)
    if st.button("Remover Oferta"):
        conn.execute(f"DELETE FROM jornal WHERE id={idxj}"); conn.commit(); st.rerun()
