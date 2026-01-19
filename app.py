import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO E ESTILO ---
st.set_page_config(page_title="CRM Representante", layout="wide")
st.markdown("<style>header, footer, #MainMenu {visibility: hidden !important;}</style>", unsafe_allow_html=True)

DB_NAME = "crm_representante_v2026.db"

# --- 2. BANCO DE DADOS (UNIFICADO) ---
def run_db(query, params=()):
    with sqlite3.connect(DB_NAME, timeout=30) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor

def query_db(query, params=()):
    with sqlite3.connect(DB_NAME, timeout=30) as conn:
        return pd.read_sql(query, conn, params=params)

# Inicialização das Tabelas (Unindo as duas lógicas)
run_db("""CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, nome TEXT, fone TEXT)""")

run_db("""CREATE TABLE IF NOT EXISTS pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER, data TEXT, 
    codigo_prod TEXT, nome_prod TEXT, qtde REAL, preco_unit REAL, lote TEXT)""")

run_db("""CREATE TABLE IF NOT EXISTS ofertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT, codigo_prod TEXT, nome_prod TEXT, 
    preco_oferta REAL, validade TEXT, edicao TEXT, lote TEXT)""")

# --- 3. MOTOR DE EXTRAÇÃO (O MELHOR DOS DOIS MUNDOS) ---
def extrair_dados_pdf(file):
    lista = []
    cliente = {"nome": "Desconhecido", "fone": "", "codigo": "000"}
    
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            txt = page.extract_text()
            if not txt: continue
            
            # Captura de cabeçalho (Nome Fantasia e Fone)
            if cliente["nome"] == "Desconhecido":
                m_c = re.search(r"Nome Fantasia:\s*(.*)", txt)
                if m_c: cliente["nome"] = m_c.group(1).split('\n')[0].strip()
                m_f = re.search(r"Fone:\s*(\d+)", txt)
                if m_f: cliente["fone"] = m_f.group(1).strip()
                m_cod = re.search(r"Cliente:\s*(\d+)", txt)
                if m_cod: cliente["codigo"] = m_cod.group(1).strip()

            # Captura de Produtos (SKU + Preço)
            for linha in txt.split('\n'):
                sku_m = re.search(r"\b(\d{4,7})\b", linha)
                if sku_m:
                    sku = sku_m.group(1)
                    precos = re.findall(r"(\d{1,3}(?:\.\d{3})*,\d{2})", linha)
                    if precos:
                        valor = float(precos[-1].replace('.', '').replace(',', '.'))
                        # Tenta pegar qtde se houver (padrão pedido)
                        lista.append({"sku": sku, "nome": linha[:40].strip(), "preco": valor})
    return cliente, lista

# --- 4. INTERFACE ---
st.title("📊 CRM Representante Comercial")

menu = st.sidebar.radio("Menu Principal", [
    "📥 Importar Pedido DEPECIL",
    "📰 Jornal de Ofertas PR",
    "🔥 Cruzar Ofertas",
    "📊 Histórico e Gestão"
])

# ================= 1. PEDIDO =================
if menu == "📥 Importar Pedido DEPECIL":
    st.header("Importar Pedido PDF")
    pdf = st.file_uploader("Selecione o PDF do pedido", type=["pdf"], key="up_ped")

    if pdf:
        # Alerta de duplicidade por lote (arquivo)
        existe = query_db("SELECT COUNT(*) as total FROM pedidos WHERE lote = ?", (pdf.name,))['total'][0]
        if existe > 0:
            st.warning(f"⚠️ O arquivo '{pdf.name}' já foi processado anteriormente.")

        if st.button("Processar e Salvar Pedido"):
            with st.spinner("Extraindo dados..."):
                cli_data, itens = extrair_dados_pdf(pdf)
                
                # Salva/Atualiza Cliente
                cur = run_db("INSERT INTO clientes (codigo, nome, fone) VALUES (?,?,?)", 
                            (cli_data["codigo"], cli_data["nome"], cli_data["fone"]))
                cliente_id = cur.lastrowid

                # Salva Pedidos em Bloco
                hoje = datetime.now().strftime("%Y-%m-%d")
                with sqlite3.connect(DB_NAME) as conn:
                    for i in itens:
                        conn.execute("""INSERT INTO pedidos (cliente_id, data, codigo_prod, nome_prod, preco_unit, lote) 
                                     VALUES (?,?,?,?,?,?)""", 
                                     (cliente_id, hoje, i["sku"], i["nome"], i["preco"], pdf.name))
                st.success(f"Pedido de '{cli_data['nome']}' importado com sucesso!")

# ================= 2. JORNAL =================
elif menu == "📰 Jornal de Ofertas PR":
    st.header("Importar Jornal PR")
    
    col_a, col_b = st.columns(2)
    with col_a:
        edicao = st.text_input("Edição (ex: 126)")
    with col_b:
        # Seletor Dinâmico de Dias (+/-)
        if "d" not in st.session_state: st.session_state.d = 7
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1: 
            if st.button("➖"): st.session_state.d = max(1, st.session_state.d - 1)
        with c2: 
            st.markdown(f"<h3 style='text-align:center'>{st.session_state.d} Dias</h3>", unsafe_allow_html=True)
        with c3: 
            if st.button("➕"): st.session_state.d += 1
        validade_dt = (datetime.now() + timedelta(days=st.session_state.d)).strftime("%Y-%m-%d")

    pdf_j = st.file_uploader("Selecione o PDF do Jornal (Matriz ou Compilado)", type=["pdf"])

    if st.button("Ativar Ofertas") and pdf_j
