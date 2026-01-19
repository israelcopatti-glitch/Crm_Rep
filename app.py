import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from fpdf import FPDF
import urllib.parse
import matplotlib.pyplot as plt
from io import BytesIO

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="AM Representações CRM", layout="wide")

# --- BANCO DE DADOS EM PORTUGUÊS ---
conn = sqlite3.connect("crm.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    cnpj TEXT UNIQUE,
    telefone TEXT
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER,
    produto TEXT,
    sku TEXT,
    quantidade REAL,
    preco_unit REAL,
    preco_total REAL,
    data TEXT,
    FOREIGN KEY(cliente_id) REFERENCES clientes(id)
);
""")
conn.commit()

# --- MOTOR DE LEITURA DE PEDIDOS (DEPECIL) ---
def extrair_dados_pdf_portugues(arquivo):
    dados = []
    nome_fantasia = "Cliente Geral"
    fone = ""
    
    with pdfplumber.open(arquivo) as pdf:
        texto_completo = ""
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"
        
        # Tradução da lógica de busca no cabeçalho
        match_nome = re.search(r"Nome Fantasia:\s*(.*)", texto_completo)
        if match_nome: nome_fantasia = match_nome.group(1).split('\n')[0].strip()
        
        match_fone = re.search(r"Fone:\s*([\d\s\-]+)", texto_completo)
        if match_fone: fone = "".join(re.findall(r'\d+', match_fone.group(1)))

        linhas = texto_completo.split("\n")
        for linha in linhas:
            partes = linha.split()
            # Identifica produto pelo SKU (numérico)
            if len(partes) >= 6 and partes[0].isdigit():
                sku = partes[0]
                precos = [p for p in partes if "," in p]
                if len(precos) >= 2:
                    try:
                        p_unit = float(precos[-2].replace(".", "").replace(",", "."))
                        p_total = float(precos[-1].replace(".", "").replace(",", "."))
                        nome_prod = " ".join(partes[1:partes.index(precos[0])])
                        
                        dados.append({
                            "produto": nome_prod, 
                            "sku": sku,
                            "preco_unit": p_unit, 
                            "preco_total": p_total
                        })
                    except: continue
    return pd.DataFrame(dados), nome_fantasia, fone

# --- INTERFACE TOTALMENTE EM PORTUGUÊS ---
st.title("🚀 AM Representações - Sistema de Gestão")

# Menu Lateral Traduzido
menu = st.sidebar.selectbox("Escolha uma Opção:", [
    "📥 Importar Pedido PDF", 
    "📊 Relatórios de Vendas", 
    "👥 Meus Clientes", 
    "⚠️ Alertas de Inatividade",
    "📝 Gerar Documento PDF"
])

# 1) IMPORTAR PEDIDO
if menu == "📥 Importar Pedido PDF":
    st.header("📄 Importar Novo Pedido")
    arquivo_pdf = st.file_uploader("Selecione o arquivo PDF do pedido", type=["pdf"])

    if arquivo_pdf:
        df, nome_cliente, fone = extrair_dados_pdf_portugues(arquivo_pdf)
        
        if not df.empty:
            st.success(f"✅ Pedido Identificado: {nome_cliente}")
