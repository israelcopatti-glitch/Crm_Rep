import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# --- 1. INTERFACE E BLOQUEIO ---
st.set_page_config(page_title="AM CRM", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>
    header, footer, #MainMenu, .stDeployButton {visibility: hidden; display: none !important;}
    [data-testid="stHeader"] {display: none !important;}
    .block-container {padding-top: 1rem !important;}
</style>""", unsafe_allow_html=True)

# --- 2. BANCO DE DADOS (NOME NOVO PARA ELIMINAR O ERRO) ---
def conectar_seguro():
    # Mudança de nome para limpar o erro OperationalError
    conn = sqlite3.connect("am_crm_v2026_final.db", check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, 
        produto TEXT, qtde REAL, preco REAL, data TEXT, UNIQUE(cliente, sku, data, preco))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS jornal (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, produto TEXT, 
        preco_oferta REAL, validade TEXT, UNIQUE(sku, preco_oferta, validade))""")
    conn.commit()
    return conn

db = conectar_seguro()

# --- 3. MOTOR DE LEITURA (DADOS REAIS: NOME E FONE) ---
def extrair_pdf(file):
    lista = []
    cli, fon = "Cliente", ""
    with pdfplumber.open(file) as pdf:
        txt = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        m_c = re.search(r"Nome Fantasia:\s*(.*)", txt); cli = m_c.group(1).split('\n')[0].strip() if m_c else cli
        m_f = re.search(r"Fone:\s*(\d+)", txt); fon = m_f.group(1).strip() if m_f else ""
        for l in txt.split("\n"):
            if re.match(r"^\d{4,7}\s+", l):
                pts = l.split()
                v = [x for x in pts if "," in x]
                if len(v) >= 4:
                    try:
                        idx_f = pts.index(v[0])
                        lista.append({
                            "cliente": cli, "fone": fon, "sku": pts[0], 
                            "produto": " ".join(pts[1:idx_f]), 
                            "qtde": float(v[-3].replace(".", "").replace(",", ".")), 
                            "preco": float(v[-2].replace(".", "").replace(",", "."))
                        })
                    except: continue
    return pd.DataFrame(lista)

# --- 4. INTERFACE ---
st.title("🚀 AM Representações")
t1, t2, t3, t4, t5 = st.tabs(["📥 Pedido", "📰 Jornal", "🔥 Cruzar", "📊 Histórico", "📋 Ofertas"])

with t1:
    if "pk" not in st.session_state: st.session_state.pk = 0
    f = st.file_uploader("Subir Pedido", type="pdf", key=f"p_{st.session_state.pk}")
    if f:
        df = extrair_pdf(f)
        if not df.empty:
            st.success(f"✅ Cliente: {df['cliente'].iloc[0]} | Fone: {df['fone'].iloc[0]}")
            st.table(df[["sku", "produto", "qtde", "preco"]])
            if st.button("💾 Salvar no Histórico"):
                for _, r in df.iterrows():
                    try:
                        db.execute("INSERT OR IGNORE INTO historico (cliente, fone, sku, produto, qtde, preco, data) VALUES (?,?,?,?,?,?,?)",
                                  (r['cliente'], r['fone'], r['sku'], r['produto'], r['qtde'], r['preco'], datetime.now().strftime("%Y-%m-%d")))
                    except: pass
                db.commit()
                st.session_state.pk += 1 # Limpa tela
                st.rerun()

with t2:
    if "jk" not in st.session_state: st.session_state.jk = 0
    val_ind = st.date_input("Vencimento deste Jornal:", datetime.now() + timedelta(days=7))
    fj = st.file_uploader("Subir Jornal", type="pdf", key=f"j_{st.session_state.jk}")
    if fj and st.button("Ativar Ofertas"):
        dfj = extrair_pdf(fj)
        if not dfj.empty:
            for _, r in dfj.iterrows():
                try:
                    db.execute("INSERT OR IGNORE INTO jornal (sku, produto, preco_oferta, validade) VALUES (?,?,?,?)",
                              (r['sku'], r['produto'], r['preco'], val_ind.strftime("%Y-%m-%d")))
                except: pass
            db.commit()
            st.session_state.jk += 1 # Limpa tela
            st.rerun()

with t3:
    # Comando de limpeza protegido para evitar o OperationalError
    try:
        db.execute("DELETE FROM jornal WHERE validade < DATE('now')")
        db.commit()
    except: pass
    
    h = pd.read_sql("SELECT * FROM historico", db)
    o = pd.read_sql("SELECT * FROM jornal", db)
    if not o.empty and not h.empty:
        c = pd.merge(o, h, on="sku", suffixes=('_j', '_h'))
        opt = c[c['preco_oferta'] < c['preco']].drop_duplicates(subset=['cliente', 'sku'])
        st.dataframe(opt[['cliente', 'produto_j', 'preco', 'preco_oferta', 'validade']], use_container_width=True)
    else:
        st.info("Suba um Pedido e um Jornal para ver o cruzamento.")

with t4:
    clis = pd.read_sql("SELECT DISTINCT cliente FROM historico", db)
    if not clis.empty:
        sel = st.selectbox("Filtrar Cliente:", ["Todos"] + clis['cliente'].tolist())
        q = f"SELECT * FROM historico" + (f" WHERE cliente='{sel}'" if sel != "Todos" else "") + " ORDER BY id DESC"
        st.dataframe(pd.read_sql(q, db), use_container_width=True)
        idx_del = st.number_input("ID p/ excluir pedido:", min_value=0, step=1)
        if st.button("🗑️ Excluir Item"):
            db.execute(f"DELETE FROM historico WHERE id={idx_del}"); db.commit(); st.rerun()

with t5:
    st.dataframe(pd.read_sql("SELECT * FROM jornal ORDER BY validade ASC", db), use_container_width=True)
    idx_j_del = st.number_input("ID p/ excluir oferta:", min_value=0, step=1)
    if st.button("🗑️ Remover Oferta"):
        db.execute(f"DELETE FROM jornal WHERE id={idx_j_del}"); db.commit(); st.rerun()
