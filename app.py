import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="AM CRM", layout="wide")
st.markdown("<style>header, footer, #MainMenu {visibility: hidden !important;}</style>", unsafe_allow_html=True)

# --- 2. BANCO DE DADOS (CONEXÃO RÁPIDA) ---
def init_db():
    conn = sqlite3.connect("am_v2026_fast.db", check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, 
        produto TEXT, qtde REAL, preco REAL, data TEXT, UNIQUE(cliente, sku, data, preco))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS jornal (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, produto TEXT, 
        preco_oferta REAL, validade TEXT, UNIQUE(sku, preco_oferta, validade))""")
    conn.commit()
    return conn

db = init_db()

# --- 3. MOTOR DE EXTRAÇÃO (ANÁLISE DE DADOS REAIS) ---
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
                            lista.append({
                                "cliente": cli, "fone": fon, "sku": pts[0].strip(), 
                                "produto": " ".join(pts[1:idx]), 
                                "qtde": float(v[-3].replace(".", "").replace(",", ".")), 
                                "preco": float(v[-2].replace(".", "").replace(",", "."))
                            })
                        except: continue
    return pd.DataFrame(lista)

# --- 4. INTERFACE ---
st.title("AM Representações")
t1, t2, t3, t4, t5 = st.tabs(["📥 Pedido", "📰 Jornal", "🔥 Cruzar", "📊 Histórico", "📋 Ofertas"])

with t1:
    if "pk" not in st.session_state: st.session_state.pk = 0
    f = st.file_uploader("Subir Pedido", type="pdf", key=f"p_{st.session_state.pk}")
    if f:
        df = extrair_pdf(f)
        if not df.empty:
            st.info(f"Cliente: {df['cliente'].iloc[0]}")
            if st.button("💾 SALVAR PEDIDO"):
                hoje = datetime.now().strftime("%Y-%m-%d")
                for _, r in df.iterrows():
                    db.execute("INSERT OR IGNORE INTO historico (cliente, fone, sku, produto, qtde, preco, data) VALUES (?,?,?,?,?,?,?)", 
                              (r['cliente'], r['fone'], r['sku'], r['produto'], r['qtde'], r['preco'], hoje))
                db.commit()
                st.session_state.pk += 1
                st.rerun()

with t2:
    st.subheader("Prazo do Jornal")
    # INTERFACE SIMPLIFICADA: - X DIAS +
    if "dias" not in st.session_state: st.session_state.dias = 7
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("➖ 1 Dia"): st.session_state.dias = max(1, st.session_state.dias - 1)
    with col2:
        st.markdown(f"<h3 style='text-align: center;'>{st.session_state.dias} Dias</h3>", unsafe_allow_html=True)
    with col3:
        if st.button("➕ 1 Dia"): st.session_state.dias += 1

    data_vencimento = (datetime.now() + timedelta(days=st.session_state.dias)).strftime("%Y-%m-%d")
    st.caption(f"Vencimento calculado: {datetime.strptime(data_vencimento, '%Y-%m-%d').strftime('%d/%m/%Y')}")

    if "jk" not in st.session_state: st.session_state.jk = 0
    fj = st.file_uploader("Subir Jornal", type="pdf", key=f"j_{st.session_state.jk}")
    
    if fj and st.button("🚀 ATIVAR OFERTAS AGORA"):
        dfj = extrair_pdf(fj)
        if not dfj.empty:
            for _, r in dfj.iterrows():
                db.execute("INSERT OR IGNORE INTO jornal (sku, produto, preco_oferta, validade) VALUES (?,?,?,?)", 
                          (r['sku'], r['produto'], r['preco'], data_vencimento))
            db.commit()
            st.success(f"Ativado! {len(dfj)} itens valendo por {st.session_state.dias} dias.")
            st.session_state.jk += 1
            st.rerun()

with t3:
    # CRUZAMENTO DE DADOS (O VÍDEO DA LÓGICA)
    db.execute("DELETE FROM jornal WHERE validade < DATE('now')")
    db.commit()
    q = """SELECT h.cliente, h.fone, j.produto, h.preco as antigo, j.preco_oferta as novo, j.validade 
           FROM jornal j INNER JOIN historico h ON j.sku = h.sku 
           WHERE j.preco_oferta < h.preco GROUP BY h.cliente, j.sku"""
    df_c = pd.read_sql(q, db)
    if not df_c.empty:
        st.dataframe(df_c, use_container_width=True)
    else:
        st.warning("Nenhuma oferta ativa coincide com o histórico.")

with t4:
    clis = pd.read_sql("SELECT DISTINCT cliente FROM historico", db)
    if not clis.empty:
        sel = st.selectbox("Cliente:", ["Todos"] + clis['cliente'].tolist())
        query = f"SELECT * FROM historico" + (f" WHERE cliente='{sel}'" if sel != "Todos" else "") + " ORDER BY id DESC"
        st.dataframe(pd.read_sql(query, db), use_container_width=True)
        idx = st.number_input("ID p/ apagar:", min_value=0, step=1)
        if st.button("Apagar Registro"):
            db.execute(f"DELETE FROM historico WHERE id={idx}")
            db.commit()
            st.rerun()

with t5:
    st.dataframe(pd.read_sql("SELECT * FROM jornal ORDER BY validade ASC", db), use_container_width=True)
    idxj = st.number_input("ID oferta p/ apagar:", min_value=0, step=1, key="del_j")
    if st.button("Remover Oferta"):
        db.execute(f"DELETE FROM jornal WHERE id={idxj}")
        db.commit()
        st.rerun()
