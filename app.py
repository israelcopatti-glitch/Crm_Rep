import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="AM CRM", layout="wide")
st.markdown("<style>header, footer, #MainMenu {visibility: hidden !important;}</style>", unsafe_allow_html=True)

DB_NAME = "am_final_v1.db"

# --- 2. FUNÇÕES DE BANCO DE DADOS (ULTRA SEGURAS) ---
def execute_db(query, params=()):
    with sqlite3.connect(DB_NAME, timeout=30) as conn:
        conn.execute("PRAGMA journal_mode=WAL") # Modo de alta performance
        conn.execute(query, params)
        conn.commit()

def query_db(query):
    with sqlite3.connect(DB_NAME, timeout=30) as conn:
        return pd.read_sql(query, conn)

# Inicialização do Banco
execute_db("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, produto TEXT, qtde REAL, preco REAL, data TEXT, lote TEXT)")
execute_db("CREATE TABLE IF NOT EXISTS jornal (id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, produto TEXT, preco_oferta REAL, validade TEXT, lote TEXT)")

# --- 3. MOTOR DE EXTRAÇÃO (OTIMIZADO) ---
def extrair_dados(file):
    lista = []
    cli, fon = "Cliente", ""
    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                txt = page.extract_text()
                if not txt: continue
                
                # Captura dados do cliente no início
                if cli == "Cliente":
                    m_c = re.search(r"Nome Fantasia:\s*(.*)", txt)
                    if m_c: cli = m_c.group(1).split('\n')[0].strip()
                    m_f = re.search(r"Fone:\s*(\d+)", txt)
                    if m_f: fon = m_f.group(1).strip()
                
                # Captura produtos
                for l in txt.split("\n"):
                    if re.match(r"^\d{4,7}\s+", l):
                        pts = l.split()
                        v = [x for x in pts if "," in x]
                        if len(v) >= 4:
                            try:
                                idx = pts.index(v[0])
                                lista.append({
                                    "sku": pts[0].strip(),
                                    "prod": " ".join(pts[1:idx]),
                                    "prc": float(v[-2].replace(".", "").replace(",", "."))
                                })
                            except: continue
        return lista, cli, fon
    except Exception as e:
        st.error(f"Erro ao ler PDF: {e}")
        return [], "", ""

# --- 4. INTERFACE ---
st.title("AM Representações")
tabs = st.tabs(["📥 Pedido", "📰 Jornal", "🔥 Cruzar", "📊 Histórico", "📋 Ofertas"])

with tabs[0]: # PEDIDO
    f_ped = st.file_uploader("Upload Pedido", type="pdf", key="up_p")
    if f_ped:
        itens, cliente, fone = extrair_dados(f_ped)
        if itens:
            st.success(f"Pedido Lido: {cliente}")
            if st.button("💾 CONFIRMAR E SALVAR PEDIDO"):
                hoje = datetime.now().strftime("%Y-%m-%d")
                with sqlite3.connect(DB_NAME) as conn:
                    for i in itens:
                        conn.execute("INSERT INTO historico (cliente, fone, sku, produto, preco, data, lote) VALUES (?,?,?,?,?,?,?)",
                                   (cliente, fone, i['sku'], i['prod'], i['prc'], hoje, f_ped.name))
                st.rerun()

with tabs[1]: # JORNAL
    st.subheader("Configurar Jornal")
    if "dias" not in st.session_state: st.session_state.dias = 7
    
    c1, c2, c3 = st.columns([1,1,1])
    with c1: 
        if st.button("➖ 1 Dia"): st.session_state.dias = max(1, st.session_state.dias - 1)
    with c2: 
        st.markdown(f"<h3 style='text-align:center'>{st.session_state.dias} Dias</h3>", unsafe_allow_html=True)
    with c3: 
        if st.button("➕ 1 Dia"): st.session_state.dias += 1
    
    data_venc = (datetime.now() + timedelta(days=st.session_state.dias)).strftime("%Y-%m-%d")
    
    f_jor = st.file_uploader("Upload Jornal", type="pdf", key="up_j")
    if f_jor:
        # Mostra o botão de ativar apenas se o arquivo for carregado
        if st.button("🚀 ATIVAR OFERTAS DESTE ARQUIVO"):
            with st.spinner("Processando..."):
                itens_j, _, _ = extrair_dados(f_jor)
                if itens_j:
                    with sqlite3.connect(DB_NAME) as conn:
                        for j in itens_j:
                            conn.execute("INSERT INTO jornal (sku, produto, preco_oferta, validade, lote) VALUES (?,?,?,?,?)",
                                       (j['sku'], j['prod'], j['prc'], data_venc, f_jor.name))
                    st.success(f"Sucesso! {len(itens_j)} ofertas ativadas.")
                    st.rerun()
                else:
                    st.error("Não encontramos produtos neste PDF. Verifique o formato.")

with tabs[2]: # CRUZAR
    # Cruzamento DIRETO por SQL (Mais rápido do mundo)
    q = """SELECT h.cliente, h.fone, j.produto, h.preco as preco_antigo, j.preco_oferta, j.validade, j.lote
           FROM jornal j INNER JOIN historico h ON j.sku = h.sku 
           WHERE j.preco_oferta < h.preco GROUP BY h.cliente, j.sku"""
    res = query_db(q)
    if not res.empty:
        st.dataframe(res, use_container_width=True)
    else:
        st.info("Nenhuma oferta ativa é menor que o histórico de compras.")

with tabs[4]: # OFERTAS (GERENCIAR LOTES)
    st.subheader("Jornais Carregados")
    lotes = query_db("SELECT lote, validade, COUNT(*) as itens FROM jornal GROUP BY lote")
    if not lotes.empty:
        st.table(lotes)
        lote_del = st.selectbox("Selecione para remover:", lotes['lote'].tolist())
        if st.button("🗑️ Excluir Arquivo"):
            execute_db("DELETE FROM jornal WHERE lote=?", (lote_del,))
            st.rerun()
