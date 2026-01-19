import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime

# --- CONFIGURAÇÃO E BLOQUEIO DE INTERFACE ---
st.set_page_config(page_title="AM CRM", layout="wide", initial_sidebar_state="collapsed")

# CSS para esconder o menu, rodapé e a barra 'Gerenciar aplicativo'
st.markdown("""
    <style>
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    header {visibility: hidden !important;}
    .stDeployButton {display:none !important;}
    [data-testid="managed_by_streamlit"] {display: none !important;}
    div[data-testid="stStatusWidget"] {visibility: hidden !important;}
    </style>
""", unsafe_allow_html=True)

# --- BANCO DE DADOS ---
conn = sqlite3.connect("crm_vendas_am.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        cliente TEXT, sku TEXT, produto TEXT, 
        quantidade REAL, preco REAL, data TEXT
    )
""")
conn.commit()

def extrair_dados_depecil(arquivo):
    dados = []
    cliente = "Desconhecido"
    
    with pdfplumber.open(arquivo) as pdf:
        texto_completo = ""
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"
        
        # 1. Identifica o Cliente (conforme o PDF real)
        m_cliente = re.search(r"Nome Fantasia:\s*(.*)", texto_completo)
        if m_cliente:
            cliente = m_cliente.group(1).split('\n')[0].strip()

        # 2. Processa as linhas do produto
        linhas = texto_completo.split("\n")
        for linha in linhas:
            # Detecta a linha que começa com o código (ex: 37050)
            if re.match(r"^\d{4,6}\s+", linha):
                # O PDF da Depecil mistura o nome com os números. 
                # Vamos usar regex para separar o SKU, o Nome e os valores finais.
                match = re.search(r"^(\d+)\s+(.*?)\s+(\d+,\d+)\s+(\d+,\d+)\s+(\w+)\s+(\d+,\d+)\s+([\d,.]+)\s+([\d,.]+)", linha)
                
                if match:
                    sku = match.group(1)
                    nome_prod = match.group(2)
                    quantidade = float(match.group(6).replace(",", "."))
                    v_unitario = float(match.group(7).replace(".", "").replace(",", "."))
                    
                    dados.append({
                        "SKU": sku,
                        "Produto": nome_prod,
                        "Quantidade": quantidade,
                        "Preço": v_unitario,
                        "Cliente": cliente
                    })
    return pd.DataFrame(dados)

# --- INTERFACE ---
st.title("🚀 AM Representações - CRM")

arquivo_pdf = st.file_uploader("Upload do Pedido Depecil", type="pdf")

if arquivo_pdf:
    df = extrair_dados_depecil(arquivo_pdf)
    if not df.empty:
        st.success(f"✅ Cliente Identificado: {df['Cliente'].iloc[0]}")
        
        # Exibe os dados exatamente como você precisa
        st.table(df[["SKU", "Produto", "Quantidade", "Preço"]])
        
        if st.button("💾 Salvar no Histórico"):
            for _, r in df.iterrows():
                cursor.execute("""
                    INSERT INTO historico (cliente, sku, produto, quantidade, preco, data) 
                    VALUES (?, ?, ?, ?, ?, DATE('now'))
                """, (r['Cliente'], r['SKU'], r['Produto'], r['Quantidade'], r['Preço']))
            conn.commit()
            st.balloons()
            st.success("Dados salvos com sucesso!")
    else:
        st.error("Não foi possível extrair os dados. Verifique se o PDF é o original da Depecil.")

