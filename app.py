import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# --- 1. INTERFACE PROFISSIONAL (BLOQUEADA) ---
st.set_page_config(page_title="AM CRM", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>
    header, footer, #MainMenu, .stDeployButton {visibility: hidden; display: none !important;}
    [data-testid="managed_by_streamlit"], [data-testid="stHeader"] {display: none !important;}
    .block-container {padding-top: 1rem !important;}
</style>""", unsafe_allow_html=True)

# --- 2. CONEXÃO OTIMIZADA (EVITA LENTIDÃO) ---
@st.cache_resource
def conectar_banco():
    conn = sqlite3.connect("am_crm_vFinal.db", check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, 
        produto TEXT, qtde REAL, preco REAL, data TEXT, UNIQUE(cliente, sku, data, preco))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS jornal (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, produto TEXT, 
        preco_oferta REAL, validade TEXT, UNIQUE(sku, preco_oferta, validade))""")
    return conn

db = conectar_banco()

# --- 3. MOTOR DE EXTRAÇÃO RÁPIDO ---
def extrair_dados(file):
    lista = []
    cli, fon = "Cliente", ""
    try:
        with pdfplumber.open(file) as pdf:
            texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
            m_c = re.search(r"Nome Fantasia:\s*(.*)", texto); cli = m_c.group(1).split('\n')[0].strip() if m_c else cli
            m_f = re.search(r"Fone:\s*(\d+)", texto); fon = m_f.group(1).strip() if m_f else ""
            for l in texto.split("\n"):
                if re.match(r"^\d{4,7}\s+", l):
                    pts = l.split()
                    sku = pts[0]
                    v_virg = [x for x in pts if "," in x]
                    if len(v_virg) >= 4:
                        idx_n = pts.index(v_virg[0])
                        nome = " ".join(pts[1:idx_n])
                        lista.append({
                            "cliente": cli, "fone": fon, "sku": sku, "produto": nome, 
                            "qtde": float(v_virg[-3].replace(".", "").replace(",", ".")), 
                            "preco": float(v_virg[-2].replace(".", "").replace(",", "."))
                        })
    except: pass
    return pd.DataFrame(lista)

# --- 4. ABAS DE NAVEGAÇÃO ---
st.title("🚀 AM Representações")
t1, t2, t3, t4, t5 = st.tabs(["📥 Novo Pedido", "📰 Novo Jornal", "🔥 Cruzar", "📊 Histórico", "📋 Ofertas"])

with t1:
    if "key_p" not in st.session_state: st.session_state.key_p = 0
    f = st.file_uploader("PDF do Pedido", type="pdf", key=f"p_{st.session_state.key_p}")
    if f:
        df = extrair_dados(f)
        if not df.empty:
            st.success(f"✅ Cliente: {df['cliente'].iloc[0]}")
            st.table(df[["sku", "produto", "qtde", "preco"]])
            if st.button("💾 Salvar e Sair da Tela"):
                for _, r in df.iterrows():
                    try:
                        db.execute("INSERT INTO historico (cliente, fone, sku, produto, qtde, preco, data) VALUES (?,?,?,?,?,?,?)",
                                  (r['cliente'], r['fone'], r['sku'], r['produto'], r['qtde'], r['preco'], datetime.now().strftime("%Y-%m-%d")))
                    except: pass
                db.commit()
                st.session_state.key_p += 1 # Limpa a tela automaticamente
                st.rerun()

with t2:
    if "key_j" not in st.session_state: st.session_state.key_j = 0
    val_hoje = st.date_input("Validade deste Jornal:", datetime.now() + timedelta(days=7))
    fj = st.file_uploader("PDF do Jornal", type="pdf", key=f"j_{st.session_state.key_j}")
    if fj and st.button("Ativar Ofertas"):
        dfj = extrair_dados(fj)
        if not dfj.empty:
            for _, r in dfj.iterrows():
                try:
                    db.execute("INSERT INTO jornal (sku, produto, preco_oferta, validade) VALUES (?,?,?,?)",
                              (r['sku'], r['produto'], r['preco'], val_hoje.strftime("%Y-%m-%d")))
                except: pass
            db.commit()
            st.session_state.key_j += 1 # Limpa a tela automaticamente
            st.rerun()

with t3:
    st.subheader("🔥 Melhores Ofertas para Clientes")
    db.execute("DELETE FROM jornal WHERE validade < DATE('now')") # Limpa vencidos
    h = pd.read_sql("SELECT * FROM historico", db)
    o = pd.read_sql("SELECT * FROM jornal", db)
    if not o.empty and not h.empty:
        c = pd.merge(o, h, on="sku", suffixes=('_j', '_h'))
        opt = c[c['preco_oferta'] < c['preco']].drop_duplicates(subset=['cliente', 'sku'])
        st.dataframe(opt[['cliente', 'produto_j', 'preco', 'preco_oferta', 'validade']], use_container_width=True)

with t4:
    st.subheader("📊 Histórico (6 Meses)")
    clis = pd.read_sql("SELECT DISTINCT cliente FROM historico", db)
    if not clis.empty:
        sel = st.selectbox("Filtrar por Cliente:", ["Todos"] + clis['cliente'].tolist())
        q = f"SELECT * FROM historico" + (f" WHERE cliente='{sel}'" if sel != "Todos" else "") + " ORDER BY id DESC"
        df_h = pd.read_sql(q, db)
        idx = st.number_input("ID do item para excluir:", min_value=0, step=1)
        if st.button("🗑️ Excluir Item"):
            db.execute(f"DELETE FROM historico WHERE id={idx}"); db.commit(); st.rerun()
        st.dataframe(df_h, use_container_width=True)

with t5:
    st.subheader("📋 Gestão do Jornal Atual")
    df_j = pd.read_sql("SELECT * FROM jornal ORDER BY validade ASC", db)
    idx_j = st.number_input("ID da oferta para remover:", min_value=0, step=1)
    if st.button("🗑️ Remover Oferta"):
        db.execute(f"DELETE FROM jornal WHERE id={idx_j}"); db.commit(); st.rerun()
    st.dataframe(df_j, use_container_width=True)
