import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO E INTERFACE ---
st.set_page_config(page_title="CRM Representante", layout="wide")
st.markdown("<style>header, footer, #MainMenu {visibility: hidden !important;}</style>", unsafe_allow_html=True)

DB_NAME = "crm_depecil_v2026.db"

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

# Inicialização das Tabelas conforme seu modelo
run_db("""CREATE TABLE IF NOT EXISTS CLIENTES (
    id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, nome TEXT, fone TEXT)""")

run_db("""CREATE TABLE IF NOT EXISTS PEDIDOS (
    id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER, data TEXT, 
    codigo_prod TEXT, nome_prod TEXT, qtde REAL, preco_unit REAL, valor_total REAL, lote TEXT)""")

run_db("""CREATE TABLE IF NOT EXISTS OFERTAS (
    id INTEGER PRIMARY KEY AUTOINCREMENT, codigo_prod TEXT, nome_prod TEXT, 
    preco_pr REAL, validade TEXT, edicao TEXT, lote TEXT)""")

# --- 3. MOTOR DE EXTRAÇÃO HÍBRIDO ---
def extrair_pdf_completo(file):
    lista = []
    cliente = {"codigo": "000", "nome": "Desconhecido", "fone": ""}
    
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            txt = page.extract_text()
            if not txt: continue
            
            # Captura de dados do cliente (lógica DEPECIL)
            if cliente["nome"] == "Desconhecido":
                m_c = re.search(r"Nome Fantasia:\s*(.*)", txt)
                if m_c: cliente["nome"] = m_c.group(1).split('\n')[0].strip()
                m_f = re.search(r"Fone:\s*(\d+)", txt)
                if m_f: cliente["fone"] = m_f.group(1).strip()
                m_cod = re.search(r"Cliente:\s*(\d+)", txt)
                if m_cod: cliente["codigo"] = m_cod.group(1).strip()

            # Captura de Itens (SKU + Preço) - Funciona para Pedido e Jornal
            for linha in txt.split('\n'):
                sku_m = re.search(r"\b(\d{4,7})\b", linha)
                if sku_m:
                    sku = sku_m.group(1)
                    precos = re.findall(r"(\d{1,3}(?:\.\d{3})*,\d{2})", linha)
                    if precos:
                        valor = float(precos[-1].replace('.', '').replace(',', '.'))
                        lista.append({
                            "codigo": sku, 
                            "nome": linha[:45].strip(), 
                            "preco": valor,
                            "qtde": 1.0 # Valor padrão se não achar
                        })
    return cliente, lista

# --- 4. NAVEGAÇÃO ---
st.title("📊 CRM Representante Comercial")

menu = st.sidebar.radio("Menu", [
    "📥 Importar Pedido DEPECIL",
    "📰 Jornal de Ofertas PR",
    "🔥 Cruzar Ofertas",
    "📋 Gestão de Lotes"
])

# ================= 1. PEDIDO =================
if menu == "📥 Importar Pedido DEPECIL":
    st.header("Importar Pedido PDF")
    pdf = st.file_uploader("Selecione o PDF do pedido", type=["pdf"])

    if pdf:
        # Alerta de duplicado (conforme solicitado: apenas aviso)
        existe = query_db("SELECT COUNT(*) as t FROM PEDIDOS WHERE lote = ?", (pdf.name,))['t'][0]
        if existe > 0:
            st.warning(f"⚠️ O arquivo '{pdf.name}' já foi importado. Deseja duplicar?")

        if st.button("Processar Pedido"):
            cli, itens = extrair_pdf_completo(pdf)
            
            # Insere/Atualiza Cliente
            cur = run_db("INSERT INTO CLIENTES (codigo, nome, fone) VALUES (?,?,?)", (cli["codigo"], cli["nome"], cli["fone"]))
            cliente_id = cur.lastrowid

            # Insere Pedidos
            hoje = datetime.now().strftime("%Y-%m-%d")
            with sqlite3.connect(DB_NAME) as conn:
                for i in itens:
                    conn.execute("""INSERT INTO PEDIDOS 
                        (cliente_id, data, codigo_prod, nome_prod, qtde, preco_unit, valor_total, lote) 
                        VALUES (?,?,?,?,?,?,?,?)""",
                        (cliente_id, hoje, i["codigo"], i["nome"], i["qtde"], i["preco"], i["preco"]*i["qtde"], pdf.name))
            st.success(f"Pedido de {cli['nome']} importado!")

# ================= 2. JORNAL =================
elif menu == "📰 Jornal de Ofertas PR":
    st.header("Importar Jornal PR")
    
    col1, col2 = st.columns(2)
    with col1:
        edicao = st.text_input("Edição", value="126")
    with col2:
        # Seletor de dias +/- Restaurado
        if "d" not in st.session_state: st.session_state.d = 7
        ca, cb, cc = st.columns([1,1,1])
        with ca: 
            if st.button("➖"): st.session_state.d = max(1, st.session_state.d - 1)
        with cb: 
            st.markdown(f"<h3 style='text-align:center'>{st.session_state.d} Dias</h3>", unsafe_allow_html=True)
        with cc: 
            if st.button("➕"): st.session_state.d += 1
        validade = (datetime.now() + timedelta(days=st.session_state.d)).strftime("%Y-%m-%d")

    pdf_j = st.file_uploader("Selecione o PDF do Jornal", type=["pdf"])

    if st.button("Processar Jornal") and pdf_j:
        with st.spinner("Lendo ofertas..."):
            _, ofertas = extrair_pdf_completo(pdf_j)
            with sqlite3.connect(DB_NAME) as conn:
                for o in ofertas:
                    conn.execute("""INSERT INTO OFERTAS 
                        (codigo_prod, nome_prod, preco_pr, validade, edicao, lote) 
                        VALUES (?,?,?,?,?,?)""",
                        (o["codigo"], o["nome"], o["preco"], validade, edicao, pdf_j.name))
            st.success(f"{len(ofertas)} ofertas importadas!")

# ================= 3. CRUZAR =================
elif menu == "🔥 Cruzar Ofertas":
    st.header("🔥 Oportunidades Encontradas")
    # Une Pedidos (Histórico) com Ofertas pelo código do produto
    q = """
    SELECT c.nome as Cliente, c.fone as WhatsApp, o.nome_prod as Produto, 
           p.preco_unit as Preco_Antigo, o.preco_pr as Preco_Oferta, o.validade
    FROM OFERTAS o
    INNER JOIN PEDIDOS p ON o.codigo_prod = p.codigo_prod
    INNER JOIN CLIENTES c ON p.cliente_id = c.id
    WHERE o.preco_pr < p.preco_unit
    AND o.validade >= DATE('now')
    GROUP BY c.nome, o.codigo_prod
    """
    df = query_db(q)
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Nenhuma oferta vantajosa encontrada para o histórico atual.")

# ================= 4. GESTÃO =================
elif menu == "📋 Gestão de Lotes":
    st.subheader("Arquivos de Jornal Ativos")
    jornais = query_db("SELECT lote, edicao, validade, COUNT(*) as total FROM OFERTAS GROUP BY lote")
    if not jornais.empty:
        st.table(jornais)
        l_del = st.selectbox("Escolha o jornal para remover:", jornais['lote'].tolist())
        if st.button("Remover Jornal Selecionado"):
            run_db("DELETE FROM OFERTAS WHERE lote=?", (l_del,))
            st.rerun()
