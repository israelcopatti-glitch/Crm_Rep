import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="AM CRM", layout="wide")
st.markdown("<style>header, footer, #MainMenu {visibility: hidden !important;}</style>", unsafe_allow_html=True)
DB_NAME = "am_crm_v3_estavel.db"

# --- BANCO DE DADOS (CONEXÃO EXPRESSA) ---
def run_db(query, params=()):
    with sqlite3.connect(DB_NAME, timeout=60) as conn: # Timeout aumentado para 60s
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()

def query_db(query):
    with sqlite3.connect(DB_NAME, timeout=60) as conn:
        return pd.read_sql(query, conn)

# Criar Tabelas
run_db("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, produto TEXT, preco REAL, data TEXT, lote TEXT)")
run_db("CREATE TABLE IF NOT EXISTS jornal (id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, produto TEXT, preco_oferta REAL, validade TEXT, lote TEXT)")

# --- MOTOR DE EXTRAÇÃO OTIMIZADO ---
def extrair_pdf_para_lista(file):
    # Esta função apenas lê, sem tocar no banco de dados (mais rápido)
    lista_temp = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            texto = page.extract_text()
            if not texto: continue
            
            linhas = texto.split('\n')
            for i, linha in enumerate(linhas):
                # Procura SKU (4 a 6 dígitos)
                sku_match = re.search(r"\b(\d{4,6})\b", linha)
                if sku_match:
                    sku = sku_match.group(1)
                    # Procura Preço na mesma linha ou na próxima
                    busca_preco = linha + " " + (linhas[i+1] if i+1 < len(linhas) else "")
                    precos = re.findall(r"(\d{1,3}(?:\.\d{3})*,\d{2})", busca_preco)
                    
                    if precos:
                        valor = float(precos[-1].replace('.', '').replace(',', '.'))
                        lista_temp.append((sku, linha[:50].strip(), valor))
    return lista_temp

# --- INTERFACE ---
st.title("AM Representações")
t1, t2, t3, t4, t5 = st.tabs(["📥 Pedido", "📰 Jornal", "🔥 Cruzar", "📊 Histórico", "📋 Ofertas"])

with t2:
    st.subheader("Ativação de Jornal")
    dias = st.select_slider("Validade em dias:", options=[3, 7, 15, 30, 60], value=7)
    dt_venc = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
    
    fj = st.file_uploader("Selecione o PDF do Jornal", type="pdf", key="up_jor")
    
    if fj:
        # Criamos um botão de processamento que só aparece após o upload
        if st.button("🚀 CONFIRMAR ATIVAÇÃO"):
            with st.spinner("Processando dados... aguarde."):
                # 1. Extração em memória
                dados_extraidos = extrair_pdf_para_lista(fj)
                
                if dados_extraidos:
                    # 2. Gravação em bloco única
                    with sqlite3.connect(DB_NAME) as conn:
                        conn.execute("PRAGMA journal_mode=WAL")
                        for d in dados_extraidos:
                            conn.execute("INSERT INTO jornal (sku, produto, preco_oferta, validade, lote) VALUES (?,?,?,?,?)",
                                       (d[0], d[1], d[2], dt_venc, fj.name))
                        conn.commit()
                    
                    st.success(f"✅ Sucesso! {len(dados_extraidos)} produtos ativos do arquivo {fj.name}")
                    st.balloons()
                else:
                    st.error("⚠️ Nenhum produto reconhecido no PDF. Verifique se o arquivo está correto.")

with t3:
    # Lógica de Cruzamento (Usando o número real do cliente)
    q = """SELECT h.cliente, h.fone as WhatsApp, j.produto, h.preco as antigo, j.preco_oferta as novo, j.validade
           FROM jornal j INNER JOIN historico h ON j.sku = h.sku 
           WHERE j.preco_oferta < h.preco GROUP BY h.cliente, j.sku"""
    df_c = query_db(q)
    if not df_c.empty:
        st.dataframe(df_c, use_container_width=True)
    else:
        st.info("Nenhuma oportunidade encontrada entre o histórico e o jornal atual.")

with t5:
    st.subheader("Gerenciar Jornais")
    lotes = query_db("SELECT lote, validade, COUNT(*) as itens FROM jornal GROUP BY lote")
    if not lotes.empty:
        st.write("Arquivos ativos no sistema:")
        st.table(lotes)
        lote_excluir = st.selectbox("Escolha um para remover:", lotes['lote'].tolist())
        if st.button("🗑️ Remover este Jornal"):
            run_db("DELETE FROM jornal WHERE lote=?", (lote_excluir,))
            st.rerun()
