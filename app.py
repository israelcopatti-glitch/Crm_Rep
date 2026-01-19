import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# --- 1. INTERFACE E BLOQUEIO ---
st.set_page_config(page_title="AM CRM", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>
    header, footer, #MainMenu, .stDeployButton {visibility: hidden !important; display: none !important;}
    [data-testid="managed_by_streamlit"], [data-testid="stHeader"] {display: none !important;}
    .block-container {padding-top: 1rem !important;}
</style>""", unsafe_allow_html=True)

# --- 2. BANCO DE DADOS (HISTÓRICO 6 MESES + ANTI-DUPLICIDADE) ---
def init_db():
    conn = sqlite3.connect("crm_am_v100.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, 
        produto TEXT, qtde REAL, preco REAL, data TEXT, UNIQUE(cliente, sku, data, preco))""")
    c.execute("""CREATE TABLE IF NOT EXISTS jornal (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, produto TEXT, 
        preco_oferta REAL, validade TEXT, UNIQUE(sku, preco_oferta, validade))""")
    conn.commit()
    return conn

db = init_db()

# --- 3. LEITURA DE PDF (NOME, QTD E FONE) ---
def ler_pdf(file):
    lista = []
    cli, fon = "Cliente", ""
    with pdfplumber.open(file) as pdf:
        txt = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        m_c = re.search(r"Nome Fantasia:\s*(.*)", txt); cli = m_c.group(1).split('\n')[0].strip() if m_c else cli
        m_f = re.search(r"Fone:\s*(\d+)", txt); fon = m_f.group(1).strip() if m_f else ""
        for l in txt.split("\n"):
            if re.match(r"^\d{4,7}\s+", l):
                pts = l.split()
                sku = pts[0]
                v_virg = [p for p in pts if "," in p]
                if len(v_virg) >= 4:
                    try:
                        idx_n = pts.index(v_virg[0])
                        nome = " ".join(pts[1:idx_n])
                        q = float(v_virg[-3].replace(".", "").replace(",", "."))
                        p = float(v_virg[-2].replace(".", "").replace(",", "."))
                        lista.append({"cliente": cli, "fone": fon, "sku": sku, "produto": nome, "qtde": q, "preco": p})
                    except: continue
    return pd.DataFrame(lista)

# --- 4. ABAS ---
st.title("🚀 AM Representações")
t1, t2, t3, t4, t5 = st.tabs(["📥 Pedido", "📰 Jornal", "🔥 Cruzar", "📊 Histórico", "📋 Ofertas"])

with t1:
    if "r_p" not in st.session_state: st.session_state.r_p = 0
    f = st.file_uploader("Suba o Pedido", type="pdf", key=f"p_{st.session_state.r_p}")
    if f:
        df = ler_pdf(f)
        if not df.empty:
            st.success(f"✅ Cliente: {df['cliente'].iloc[0]} | Fone: {df['fone'].iloc[0]}")
            st.table(df[["sku", "produto", "qtde", "preco"]])
            if st.button("💾 Salvar e Limpar"):
                cur = db.cursor()
                for _, r in df.iterrows():
                    try: cur.execute("INSERT INTO historico (cliente, fone, sku, produto, qtde, preco, data) VALUES (?,?,?,?,?,?,?)",
                                  (r['cliente'], r['fone'], r['sku'], r['produto'], r['qtde'], r['preco'], datetime.now().strftime("%Y-%m-%d")))
                    except: pass
                db.commit()
                st.session_state.r_p += 1
                st.rerun()

with t2:
    if "r_j" not in st.session_state: st.session_state.r_j = 0
    val = st.date_input("Validade:", datetime.now() + timedelta(days=7))
    fj = st.file_uploader("Suba o Jornal", type="pdf", key=f"j_{st.session_state.r_j}")
    if fj and st.button("Ativar Jornal"):
        dfj = ler_pdf(fj)
        if not dfj.empty:
            cur = db.cursor()
            for _, r in dfj.iterrows():
                try: cur.execute("INSERT INTO jornal (sku, produto, preco_oferta, validade) VALUES (?,?,?,?)",
                              (r['sku'], r['produto'], r['preco'], val.strftime("%Y-%m-%d")))
                except: pass
            db.commit()
            st.session_state.r_j += 1
            st.rerun()

with t3:
    db.execute("DELETE FROM jornal WHERE validade < ?", (datetime.now().strftime("%Y-%m-%d"),))
    dh, do = pd.read_sql("SELECT * FROM historico", db), pd.read_sql("SELECT * FROM jornal", db)
    if not do.empty and not dh.empty:
        cruz = pd.merge(do, dh, on="sku", suffixes=('_j', '_h'))
        opts = cruz[cruz['preco_oferta'] < cruz['preco']].drop_duplicates(subset=['cliente', 'sku'])
        st.dataframe(opts[['cliente', 'produto_j', 'preco', 'preco_oferta', 'validade']])

with t4:
    clis = pd.read_sql("SELECT DISTINCT cliente FROM historico", db)
    if not clis.empty:
        s = st.selectbox("Pesquisar Cliente:", ["Todos"] + clis['cliente'].tolist())
        dfh = pd.read_sql("SELECT * FROM historico" + (f" WHERE cliente='{s}'" if s!="Todos" else "") + " ORDER BY id DESC", db)
        idx_p = st.number_input("ID para apagar item:", min_value=0, step=1)
        if st.button("Excluir do Histórico"):
            db.execute(f"DELETE FROM historico WHERE id={idx_p}"); db.commit(); st.rerun()
        st.dataframe(dfh)

with t5:
    dfj_v = pd.read_sql("SELECT * FROM jornal ORDER BY validade ASC", db)
    idx_j = st.number_input("ID para apagar oferta:", min_value=0, step=1)
    if st.button("Remover do Jornal"):
        db.execute(f"DELETE FROM jornal WHERE id={idx_j}"); db.commit(); st.rerun()
    st.dataframe(dfj_v)
