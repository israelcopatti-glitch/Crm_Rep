import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="AM CRM", layout="wide")
st.markdown("<style>header, footer, #MainMenu {visibility: hidden !important;}</style>", unsafe_allow_html=True)
DB_NAME = "am_crm_v2.db"

# --- FUNÇÕES DE BANCO ---
def execute_batch(query, data_list):
    with sqlite3.connect(DB_NAME, timeout=30) as conn:
        conn.executemany(query, data_list)
        conn.commit()

def query_db(query):
    with sqlite3.connect(DB_NAME, timeout=30) as conn:
        return pd.read_sql(query, conn)

# Criar tabelas se não existirem
with sqlite3.connect(DB_NAME) as conn:
    conn.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, produto TEXT, preco REAL, data TEXT, lote TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS jornal (id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, produto TEXT, preco_oferta REAL, validade TEXT, lote TEXT)")

# --- NOVO MOTOR DE EXTRAÇÃO (MAIS PODEROSO) ---
def extrair_inteligente(file):
    lista_final = []
    cliente_detectado = "Cliente Desconhecido"
    fone_detectado = ""
    
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            texto = page.extract_text()
            if not texto: continue
            
            # 1. Detectar Cliente (apenas na primeira página)
            if cliente_detectado == "Cliente Desconhecido":
                m_c = re.search(r"Nome Fantasia:\s*(.*)", texto)
                if m_c: cliente_detectado = m_c.group(1).split('\n')[0].strip()
                m_f = re.search(r"Fone:\s*(\d+)", texto)
                if m_f: fone_detectado = m_f.group(1).strip()

            # 2. Estratégia de Captura por Linhas
            linhas = texto.split('\n')
            for i, linha in enumerate(linhas):
                # Procura por SKUs (números de 4 a 6 dígitos no início ou meio da linha)
                skus_na_linha = re.findall(r"\b(\d{4,6})\b", linha)
                
                if skus_na_linha:
                    sku = skus_na_linha[0]
                    # Tenta achar um preço (ex: 12,34) na mesma linha ou na linha de baixo
                    texto_busca = linha + " " + (linhas[i+1] if i+1 < len(linhas) else "")
                    precos = re.findall(r"(\d{1,3}(?:\.\d{3})*,\d{2})", texto_busca)
                    
                    if precos:
                        # Pega o último preço encontrado (geralmente o valor unitário final)
                        valor = float(precos[-1].replace('.', '').replace(',', '.'))
                        # Limpa o nome do produto (remove o SKU e o preço da linha)
                        prod_limpo = linha.replace(sku, "").strip()
                        
                        lista_final.append({
                            "sku": sku,
                            "produto": prod_limpo[:50], # Limita tamanho do nome
                            "preco": valor
                        })
    
    return lista_final, cliente_detectado, fone_detectado

# --- INTERFACE ---
st.title("AM Representações - Sistema de Lotes")
t1, t2, t3, t4, t5 = st.tabs(["📥 Pedido", "📰 Jornal", "🔥 Cruzar", "📊 Histórico", "📋 Ofertas"])

with t1:
    f = st.file_uploader("Subir Pedido", type="pdf", key="p")
    if f:
        itens, cli, fon = extrair_inteligente(f)
        if itens:
            st.info(f"Cliente: {cli}")
            if st.button("💾 SALVAR PEDIDO"):
                hoje = datetime.now().strftime("%Y-%m-%d")
                dados = [(cli, fon, i['sku'], i['produto'], i['preco'], hoje, f.name) for i in itens]
                execute_batch("INSERT INTO historico (cliente, fone, sku, produto, preco, data, lote) VALUES (?,?,?,?,?,?,?)", dados)
                st.success("Salvo!")

with t2:
    dias = st.number_input("Validade (Dias)", min_value=1, value=7)
    dt_venc = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
    fj = st.file_uploader("Subir Jornal (Matriz ou Compilado)", type="pdf", key="j")
    
    if fj and st.button("🚀 ATIVAR JORNAL"):
        itens_j, _, _ = extrair_inteligente(fj)
        if itens_j:
            dados_j = [(i['sku'], i['produto'], i['preco'], dt_venc, fj.name) for i in itens_j]
            execute_batch("INSERT INTO jornal (sku, produto, preco_oferta, validade, lote) VALUES (?,?,?,?,?)", dados_j)
            st.success(f"Sucesso! {len(itens_j)} itens importados do {fj.name}")
            st.rerun()
        else:
            st.error("Não encontramos produtos. O formato deste PDF é muito diferente.")

with t3:
    # Cruzamento com o número real do cliente como solicitado nas suas instruções
    q = """SELECT h.cliente, h.fone as WhatsApp, j.produto, h.preco as preco_antigo, j.preco_oferta, j.validade
           FROM jornal j INNER JOIN historico h ON j.sku = h.sku 
           WHERE j.preco_oferta < h.preco GROUP BY h.cliente, j.sku"""
    df = query_db(q)
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("Sem ofertas menores que o histórico.")

with t5:
    st.subheader("Gerenciar Arquivos")
    lotes = query_db("SELECT lote, validade, COUNT(*) as total FROM jornal GROUP BY lote")
    if not lotes.empty:
        st.table(lotes)
        lote_del = st.selectbox("Escolha o arquivo para excluir:", lotes['lote'].tolist())
        if st.button("🗑️ APAGAR ARQUIVO"):
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("DELETE FROM jornal WHERE lote=?", (lote_del,))
            st.rerun()
