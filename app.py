import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# 1. BLOQUEIO DE INTERFACE (Simples e Eficaz)
st.set_page_config(page_title="AM CRM", layout="wide")
st.markdown("<style>header, footer, #MainMenu, .stDeployButton {visibility: hidden; display: none !important;}</style>", unsafe_allow_html=True)

# 2. BANCO DE DADOS (Nome novo para evitar conflitos de cache)
def get_db():
    conn = sqlite3.connect("am_v2026_db.db", check_same_thread=False)
    conn.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, produto TEXT, qtde REAL, preco REAL, data TEXT, UNIQUE(cliente, sku, data, preco))")
    conn.execute("CREATE TABLE IF NOT EXISTS jornal (id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, produto TEXT, preco_oferta REAL, validade TEXT, UNIQUE(sku, preco_oferta, validade))")
    return conn

db = get_db()

# 3. EXTRAÇÃO DE DADOS (Calibrada para o PDF da Depecil)
def extrair(file):
    rows = []
    cli, fon = "Cliente", ""
    with pdfplumber.open(file) as pdf:
        full_text = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        m_c = re.search(r"Nome Fantasia:\s*(.*)", full_text)
        if m_c: cli = m_c.group(1).split('\n')[0].strip()
        m_f = re.search(r"Fone:\s*(\d+)", full_text)
        if m_f: fon = m_f.group(1).strip()
        
        for line in full_text.split("\n"):
            if re.match(r"^\d{4,7}\s+", line):
                p = line.split()
                v_c = [x for x in p if "," in x]
                if len(v_c) >= 4:
                    try:
                        idx_f = p.index(v_c[0])
                        rows.append({
                            "cliente": cli, "fone": fon, "sku": p[0], 
                            "produto": " ".join(p[1:idx_f]), 
                            "qtde": float(v_c[-3].replace(".", "").replace(",", ".")), 
                            "preco": float(v_c[-2].replace(".", "").replace(",", "."))
                        })
                    except: continue
    return pd.DataFrame(rows)

# 4. INTERFACE POR ABAS
st.title("AM Representações")
t1, t2, t3, t4, t5 = st.tabs(["📥 Pedido", "📰 Jornal", "🔥 Cruzar", "📊 Histórico", "📋 Ofertas"])

with t1:
    if "key_p" not in st.session_state: st.session_state.key_p = 0
    f = st.file_uploader("Suba o Pedido", type="pdf", key=f"p_{st.session_state.key_p}")
    if f:
        df = extrair(f)
        if not df.empty:
            st.table(df[["sku", "produto", "qtde", "preco"]])
            if st.button("Salvar e Limpar Tela"):
                for _, r in df.iterrows():
                    try:
                        db.execute("INSERT INTO historico (cliente, fone, sku, produto, qtde, preco, data) VALUES (?,?,?,?,?,?,?)",
                                  (r['cliente'], r['fone'], r['sku'], r['produto'], r['qtde'], r['preco'], datetime.now().strftime("%Y-%m-%d")))
                    except: pass
                db.commit()
                st.session_state.key_p += 1
                st.rerun()

with t2:
    if "key_j" not in st.session_state: st.session_state.key_j = 0
    val_ind = st.date_input("Vencimento:", datetime.now() + timedelta(days=7))
    fj = st.file_uploader("Suba o Jornal", type="pdf", key=f"j_{st.session_state.key_j}")
    if fj and st.button("Ativar Ofertas"):
        dfj = extrair(fj)
        if not dfj.empty:
            for _, r in dfj.iterrows():
                try:
                    db.execute("INSERT INTO jornal (sku, produto, preco_oferta, validade) VALUES (?,?,?,?)",
                              (r['sku'], r['produto'], r['preco'], val_ind.strftime("%Y-%m-%d")))
                except: pass
            db.commit()
            st.session_state.key_j += 1
            st.rerun()

with t3:
    db.execute("DELETE FROM jornal WHERE validade < DATE('now')")
    h = pd.read_sql("SELECT * FROM historico", db)
    o = pd.read_sql("SELECT * FROM jornal", db)
    if not o.empty and not h.empty:
        c = pd.merge(o, h, on="sku", suffixes=('_j', '_h'))
        opt = c[c['preco_oferta'] < c['preco']].drop_duplicates(subset=['cliente', 'sku'])
        st.dataframe(opt[['cliente', 'produto_j', 'preco', 'preco_oferta', 'validade']])

with t4:
    clis = pd.read_sql("SELECT DISTINCT cliente FROM historico", db)
    if not clis.empty:
        sel = st.selectbox("Cliente:", ["Todos"] + clis['cliente'].tolist())
        q = "SELECT * FROM historico" + (f" WHERE cliente='{sel}'" if sel != "Todos" else "") + " ORDER BY id DESC"
        st.dataframe(pd.read_sql(q, db))
        idx = st.number_input("ID para apagar:", min_value=0, step=1)
        if st.button("Excluir Item"):
            db.execute(f"DELETE FROM historico WHERE id={idx}")
            db.commit(); st.rerun()

with t5:
    st.dataframe(pd.read_sql("SELECT * FROM jornal ORDER BY validade ASC", db))
    idx_j = st.number_input("ID oferta para apagar:", min_value=0, step=1)
    if st.button("Excluir Oferta"):
        db.execute(f"DELETE FROM jornal WHERE id={idx_j}")
        db.commit(); st.rerun()
