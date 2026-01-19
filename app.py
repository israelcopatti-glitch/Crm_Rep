import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO E PERFORMANCE ---
st.set_page_config(page_title="AM CRM", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>
    header, footer, #MainMenu, .stDeployButton {visibility: hidden; display: none !important;}
    [data-testid="stHeader"] {display: none !important;}
    .block-container {padding-top: 1rem !important;}
</style>""", unsafe_allow_html=True)

# --- 2. BANCO DE DADOS (MODO RÁPIDO) ---
def init_db():
    conn = sqlite3.connect("am_performance_v1.db", check_same_thread=False)
    # Ativa modo de gravação ultra rápida
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

# --- 3. MOTOR DE LEITURA OTIMIZADO ---
def extrair_dados_pdf(file):
    lista_itens = []
    cli, fon = "Cliente", ""
    with pdfplumber.open(file) as pdf:
        # Processa página por página para não travar a memória
        for page in pdf.pages:
            texto = page.extract_text()
            if not texto: continue
            
            # Pega dados do cliente apenas uma vez
            if cli == "Cliente":
                m_c = re.search(r"Nome Fantasia:\s*(.*)", texto)
                if m_c: cli = m_c.group(1).split('\n')[0].strip()
                m_f = re.search(r"Fone:\s*(\d+)", texto)
                if m_f: fon = m_f.group(1).strip()
            
            # Extrai produtos
            for linha in texto.split("\n"):
                if re.match(r"^\d{4,7}\s+", linha):
                    pts = linha.split()
                    v_virg = [x for x in pts if "," in x]
                    if len(v_virg) >= 4:
                        try:
                            idx_f = pts.index(v_virg[0])
                            lista_itens.append({
                                "cliente": cli, "fone": fon, "sku": pts[0], 
                                "produto": " ".join(pts[1:idx_f]), 
                                "qtde": float(v_virg[-3].replace(".", "").replace(",", ".")), 
                                "preco": float(v_virg[-2].replace(".", "").replace(",", "."))
                            })
                        except: continue
    return pd.DataFrame(lista_itens)

# --- 4. INTERFACE ---
st.title("🚀 AM Representações")
t1, t2, t3, t4, t5 = st.tabs(["📥 Pedido", "📰 Jornal", "🔥 Cruzar", "📊 Histórico", "📋 Ofertas"])

with t1:
    if "pk" not in st.session_state: st.session_state.pk = 0
    f = st.file_uploader("Subir Pedido PDF", type="pdf", key=f"p_{st.session_state.pk}")
    if f:
        with st.spinner('Lendo PDF...'):
            df = extrair_dados_pdf(f)
        if not df.empty:
            st.success(f"✅ Pedido: {df['cliente'].iloc[0]}")
            st.table(df[["sku", "produto", "qtde", "preco"]].head(10)) # Mostra só os 10 primeiros p/ carregar rápido
            if st.button("💾 Salvar Histórico Completo"):
                with st.status("Gravando dados..."):
                    for _, r in df.iterrows():
                        try:
                            db.execute("INSERT OR IGNORE INTO historico (cliente, fone, sku, produto, qtde, preco, data) VALUES (?,?,?,?,?,?,?)",
                                      (r['cliente'], r['fone'], r['sku'], r['produto'], r['qtde'], r['preco'], datetime.now().strftime("%Y-%m-%d")))
                        except: pass
                    db.commit()
                st.session_state.pk += 1
                st.rerun()

with t2:
    if "jk" not in st.session_state: st.session_state.jk = 0
    v_date = st.date_input("Vencimento do Jornal:", datetime.now() + timedelta(days=7))
    fj = st.file_uploader("Subir Jornal PDF", type="pdf", key=f"j_{st.session_state.jk}")
    if fj and st.button("Ativar Ofertas"):
        with st.spinner('Processando Jornal...'):
            dfj = extrair_dados_pdf(fj)
            if not dfj.empty:
                for _, r in dfj.iterrows():
                    try:
                        db.execute("INSERT OR IGNORE INTO jornal (sku, produto, preco_oferta, validade) VALUES (?,?,?,?)",
                                  (r['sku'], r['produto'], r['preco'], v_date.strftime("%Y-%m-%d")))
                    except: pass
                db.commit()
                st.session_state.jk += 1
                st.rerun()

with t3:
    # Cruzamento rápido via SQL
    db.execute("DELETE FROM jornal WHERE validade < DATE('now')")
    db.commit()
    query = """
    SELECT h.cliente, j.produto as produto_jor, h.preco as preco_antigo, j.preco_oferta, j.validade
    FROM jornal j
    INNER JOIN historico h ON j.sku = h.sku
    WHERE j.preco_oferta < h.preco
    GROUP BY h.cliente, j.sku
    """
    df_cruzado = pd.read_sql(query, db)
    if not df_cruzado.empty:
        st.dataframe(df_cruzado, use_container_width=True)
    else:
        st.info("Nenhuma oportunidade encontrada no momento.")

with t4:
    clis = pd.read_sql("SELECT DISTINCT cliente FROM historico", db)
    if not clis.empty:
        sel = st.selectbox("Filtrar por Cliente:", ["Todos"] + clis['cliente'].tolist())
        q = f"SELECT * FROM historico" + (f" WHERE cliente='{sel}'" if sel != "Todos" else "") + " ORDER BY id DESC"
        st.dataframe(pd.read_sql(q, db), use_container_width=True)
        idx_del = st.number_input("ID para excluir pedido:", min_value=0, step=1)
        if st.button("🗑️ Excluir Item"):
            db.execute(f"DELETE FROM historico WHERE id={idx_del}"); db.commit(); st.rerun()

with t5:
    st.dataframe(pd.read_sql("SELECT * FROM jornal ORDER BY validade ASC", db), use_container_width=True)
    idx_j_del = st.number_input("ID para remover oferta:", min_value=0, step=1)
    if st.button("🗑️ Remover Oferta"):
        db.execute(f"DELETE FROM jornal WHERE id={idx_j_del}"); db.commit(); st.rerun()
