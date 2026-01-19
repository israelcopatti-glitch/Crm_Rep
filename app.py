import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# 1. SETUP DE INTERFACE
st.set_page_config(page_title="AM CRM", layout="wide")
st.markdown("<style>header, footer, .stDeployButton {visibility: hidden; display: none !important;}</style>", unsafe_allow_html=True)

# 2. BANCO DE DADOS COM TRATAMENTO DE ERRO DE CONEXÃO
def init_db():
    try:
        conn = sqlite3.connect("am_rep_v1.db", check_same_thread=False)
        conn.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, produto TEXT, qtde REAL, preco REAL, data TEXT, UNIQUE(cliente, sku, data, preco))")
        conn.execute("CREATE TABLE IF NOT EXISTS jornal (id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, produto TEXT, preco_oferta REAL, validade TEXT, UNIQUE(sku, preco_oferta, validade))")
        return conn
    except:
        # Se o servidor bloquear o arquivo, ele usa a memória (evita o erro "Oh No")
        return sqlite3.connect(":memory:", check_same_thread=False)

db = init_db()

# 3. EXTRAÇÃO DE DADOS (DADOS REAIS E NOME COMPLETO)
def extrair(file):
    res = []
    cli, fon = "Cliente", ""
    with pdfplumber.open(file) as pdf:
        txt = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        m_c = re.search(r"Nome Fantasia:\s*(.*)", txt); cli = m_c.group(1).split('\n')[0].strip() if m_c else cli
        m_f = re.search(r"Fone:\s*(\d+)", txt); fon = m_f.group(1).strip() if m_f else ""
        for l in txt.split("\n"):
            if re.match(r"^\d{4,7}\s+", l):
                p = l.split()
                v = [x for x in p if "," in x]
                if len(v) >= 4:
                    try:
                        idx_f = p.index(v[0])
                        res.append({"cliente": cli, "fone": fon, "sku": p[0], "produto": " ".join(p[1:idx_f]), "qtde": float(v[-3].replace(".", "").replace(",", ".")), "preco": float(v[-2].replace(".", "").replace(",", "."))})
                    except: continue
    return pd.DataFrame(res)

# 4. INTERFACE POR ABAS
st.title("AM Representações")
t1, t2, t3, t4, t5 = st.tabs(["📥 Pedido", "📰 Jornal", "🔥 Cruzar", "📊 Histórico", "📋 Ofertas"])

with t1:
    if "k1" not in st.session_state: st.session_state.k1 = 0
    f = st.file_uploader("Arquivo PDF", type="pdf", key=f"u_{st.session_state.k1}")
    if f:
        df = extrair(f)
        if not df.empty:
            st.table(df[["sku", "produto", "qtde", "preco"]])
            if st.button("Salvar Histórico"):
                for _, r in df.iterrows():
                    try: db.execute("INSERT OR IGNORE INTO historico (cliente, fone, sku, produto, qtde, preco, data) VALUES (?,?,?,?,?,?,?)", (r['cliente'], r['fone'], r['sku'], r['produto'], r['qtde'], r['preco'], datetime.now().strftime("%Y-%m-%d")))
                    except: pass
                db.commit()
                st.session_state.k1 += 1
                st.rerun()

with t2:
    if "k2" not in st.session_state: st.session_state.k2 = 0
    dt = st.date_input("Validade:", datetime.now() + timedelta(days=7))
    fj = st.file_uploader("Jornal PDF", type="pdf", key=f"j_{st.session_state.k2}")
    if fj and st.button("Ativar Ofertas"):
        dfj = extrair(fj)
        if not dfj.empty:
            for _, r in dfj.iterrows():
                try: db.execute("INSERT OR IGNORE INTO jornal (sku, produto, preco_oferta, validade) VALUES (?,?,?,?)", (r['sku'], r['produto'], r['preco'], dt.strftime("%Y-%m-%d")))
                except: pass
            db.commit()
            st.session_state.k2 += 1
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
        s = st.selectbox("Cliente:", ["Todos"] + clis['cliente'].tolist())
        q = f"SELECT * FROM historico" + (f" WHERE cliente='{s}'" if s!="Todos" else "") + " ORDER BY id DESC"
        st.dataframe(pd.read_sql(q, db))
        idx = st.number_input("ID p/ apagar:", min_value=0, step=1)
        if st.button("Excluir Pedido"):
            db.execute(f"DELETE FROM historico WHERE id={idx}"); db.commit(); st.rerun()

with t5:
    st.dataframe(pd.read_sql("SELECT * FROM jornal ORDER BY validade ASC", db))
    idxj = st.number_input("ID oferta p/ apagar:", min_value=0, step=1)
    if st.button("Excluir Oferta"):
        db.execute(f"DELETE FROM jornal WHERE id={idxj}"); db.commit(); st.rerun()
