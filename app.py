import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="AM CRM", layout="wide")
st.markdown("<style>header, footer, #MainMenu {visibility: hidden !important;}</style>", unsafe_allow_html=True)

DB_NAME = "am_crm_v_final_2026.db"

# --- 2. BANCO DE DADOS ---
def run_db(query, params=()):
    with sqlite3.connect(DB_NAME, timeout=30) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()

def query_db(query, params=()):
    with sqlite3.connect(DB_NAME, timeout=30) as conn:
        return pd.read_sql(query, conn, params=params)

# Inicialização das tabelas (Garantindo histórico e lotes)
run_db("""CREATE TABLE IF NOT EXISTS historico (
    id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, 
    produto TEXT, preco REAL, data TEXT, lote TEXT)""")

run_db("""CREATE TABLE IF NOT EXISTS jornal (
    id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, produto TEXT, 
    preco_oferta REAL, validade TEXT, lote TEXT)""")

# --- 3. MOTOR DE EXTRAÇÃO (HÍBRIDO: PEDIDO + JORNAL) ---
def extrair_pdf_completo(file):
    lista = []
    cli, fon = "Cliente", ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            txt = page.extract_text()
            if not txt: continue
            
            # Detecta Cliente e Fone Real (conforme instruções)
            if cli == "Cliente":
                m_c = re.search(r"Nome Fantasia:\s*(.*)", txt)
                if m_c: cli = m_c.group(1).split('\n')[0].strip()
                m_f = re.search(r"Fone:\s*(\d+)", txt)
                if m_f: fon = m_f.group(1).strip()
            
            for i, linha in enumerate(txt.split('\n')):
                # Busca SKU (4-6 dígitos) e Preço na linha ou vizinhança
                sku_match = re.search(r"\b(\d{4,6})\b", linha)
                if sku_match:
                    sku = sku_match.group(1)
                    # Pega o preço (formato 0,00)
                    precos = re.findall(r"(\d{1,3}(?:\.\d{3})*,\d{2})", linha)
                    if precos:
                        valor = float(precos[-1].replace('.', '').replace(',', '.'))
                        lista.append((cli, fon, sku, linha[:40].strip(), valor))
    return lista

# --- 4. INTERFACE ---
st.title("AM Representações")
t1, t2, t3, t4, t5 = st.tabs(["📥 Pedido", "📰 Jornal", "🔥 Cruzar", "📊 Histórico", "📋 Ofertas"])

with t1:
    st.subheader("Importar Pedido do Cliente")
    f_ped = st.file_uploader("Upload Pedido (PDF)", type="pdf", key="up_ped")
    if f_ped:
        dados_p = extrair_pdf_completo(f_ped)
        if dados_p:
            st.info(f"Cliente: {dados_p[0][0]} | Itens: {len(dados_p)}")
            if st.button("💾 SALVAR NO HISTÓRICO"):
                hoje = datetime.now().strftime("%Y-%m-%d")
                with sqlite3.connect(DB_NAME) as conn:
                    for d in dados_p:
                        conn.execute("INSERT INTO historico (cliente, fone, sku, produto, preco, data, lote) VALUES (?,?,?,?,?,?,?)",
                                   (d[0], d[1], d[2], d[3], d[4], hoje, f_ped.name))
                st.success("Pedido salvo no histórico de 6 meses!")
                st.rerun()

with t2:
    st.subheader("Ativar Jornal de Ofertas")
    if "d" not in st.session_state: st.session_state.d = 7
    
    # Seletor - Dias + (Restaurado conforme pedido)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("➖ 1 Dia"): st.session_state.d = max(1, st.session_state.d - 1)
    with col2:
        st.markdown(f"<h2 style='text-align: center;'>{st.session_state.d} Dias</h2>", unsafe_allow_html=True)
    with col3:
        if st.button("➕ 1 Dia"): st.session_state.d += 1
    
    dt_venc = (datetime.now() + timedelta(days=st.session_state.d)).strftime("%Y-%m-%d")
    f_jor = st.file_uploader("Upload Jornal (Matriz ou Compilado)", type="pdf", key="up_jor")
    
    if f_jor and st.button("🚀 ATIVAR JORNAL"):
        with st.spinner("Processando..."):
            dados_j = extrair_pdf_completo(f_jor)
            if dados_j:
                with sqlite3.connect(DB_NAME) as conn:
                    for d in dados_j:
                        conn.execute("INSERT INTO jornal (sku, produto, preco_oferta, validade, lote) VALUES (?,?,?,?,?)",
                                   (d[2], d[3], d[4], dt_venc, f_jor.name))
                st.success(f"Ativado: {f_jor.name} ({len(dados_j)} itens)")
                st.rerun()

with t3:
    # Cruzamento Automático
    q = """SELECT h.cliente, h.fone, j.produto, h.preco as preco_antigo, j.preco_oferta, j.validade, j.lote
           FROM jornal j INNER JOIN historico h ON j.sku = h.sku 
           WHERE j.preco_oferta < h.preco GROUP BY h.cliente, j.sku"""
    df_c = query_db(q)
    if not df_c.empty:
        st.dataframe(df_c, use_container_width=True)
    else:
        st.info("Nenhuma oferta menor que o preço do histórico foi encontrada.")

with t4:
    # Histórico de 6 meses
    clis = query_db("SELECT DISTINCT cliente FROM historico")
    if not clis.empty:
        sel = st.selectbox("Filtrar Cliente:", ["Todos"] + clis['cliente'].tolist())
        sql = "SELECT id, cliente, fone, produto, preco, data FROM historico"
        if sel != "Todos": sql += f" WHERE cliente=?"
        st.dataframe(query_db(sql + " ORDER BY id DESC", (sel,) if sel != "Todos" else ()), use_container_width=True)

with t5:
    # Gerenciar por Nome de Arquivo (Lote)
    st.subheader("Jornais Ativos")
    lotes = query_db("SELECT lote, validade, COUNT(*) as itens FROM jornal GROUP BY lote")
    if not lotes.empty:
        st.table(lotes)
        l_del = st.selectbox("Selecione o arquivo para apagar:", lotes['lote'].tolist())
        if st.button("🗑️ EXCLUIR ARQUIVO SELECIONADO"):
            run_db("DELETE FROM jornal WHERE lote=?", (l_del,))
            st.rerun()
