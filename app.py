import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime

# --- BLOQUEIO DE INTERFACE ---
st.set_page_config(page_title="AM CRM", layout="wide", initial_sidebar_state="collapsed")
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
conn = sqlite3.connect("crm_am_v6.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        cliente TEXT, sku TEXT, produto TEXT, 
        quantidade REAL, preco REAL, data TEXT
    )
""")
conn.commit()

def extrair_depecil_real(arquivo):
    dados = []
    cliente = "Não Identificado"
    
    with pdfplumber.open(arquivo) as pdf:
        texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        
        # Identifica o Cliente
        m_cliente = re.search(r"Nome Fantasia:\s*(.*)", texto)
        if m_cliente:
            cliente = m_cliente.group(1).split('\n')[0].strip()

        # Processa as linhas da tabela
        linhas = texto.split("\n")
        for linha in linhas:
            # Verifica se a linha começa com o código do produto (ex: 37050)
            if re.match(r"^\d{4,7}\s+", linha):
                partes = linha.split()
                
                # O SKU é o primeiro elemento
                [span_3](start_span)sku = partes[0][span_3](end_span)
                
                # Preços e Quantidades sempre têm vírgula no seu PDF
                # Vamos identificar onde começam os valores numéricos de impostos (0,00)
                indices_virgula = [i for i, p in enumerate(partes) if "," in p]
                
                if len(indices_virgula) >= 4:
                    # O Nome do Produto está entre o SKU e o primeiro valor com vírgula (IPI)
                    idx_ipi = indices_virgula[0]
                    [span_4](start_span)nome_prod = " ".join(partes[1:idx_ipi])[span_4](end_span)
                    
                    try:
                        # [span_5](start_span)No seu PDF[span_5](end_span): 
                        # Qtde é o valor antes do V. Unit.
                        # V. Unit é o penúltimo valor com vírgula
                        qtd_raw = partes[indices_virgula[-3]] # Ex: 60,00
                        val_raw = partes[indices_virgula[-2]] # Ex: 31,6236
                        
                        quantidade = float(qtd_raw.replace(".", "").replace(",", "."))
                        preco_unit = float(val_raw.replace(".", "").replace(",", "."))
                        
                        dados.append({
                            "Cód/SKU": sku,
                            "Produto": nome_prod,
                            "Quantidade": quantidade,
                            "Preço Pago": preco_unit,
                            "Cliente": cliente
                        })
                    except:
                        continue
    return pd.DataFrame(dados)

# --- INTERFACE USUÁRIO ---
st.title("📦 AM Representações - CRM")

arq = st.file_uploader("Suba o PDF do Pedido Depecil", type="pdf")

if arq:
    df = extrair_depecil_real(arq)
    if not df.empty:
        st.success(f"✅ Pedido de: {df['Cliente'].iloc[0]}")
        # Exibe a tabela com as colunas que você precisava
        st.table(df[["Cód/SKU", "Produto", "Quantidade", "Preço Pago"]])
        
        if st.button("💾 Salvar no Histórico"):
            for _, r in df.iterrows():
                cursor.execute("""
                    INSERT INTO historico (cliente, sku, produto, quantidade, preco, data) 
                    VALUES (?, ?, ?, ?, ?, DATE('now'))
                """, (r['Cliente'], r['Cód/SKU'], r['Produto'], r['Quantidade'], r['Preço Pago']))
            conn.commit()
            st.success("Dados salvos com sucesso!")
    else:
        st.error("O sistema não conseguiu processar as linhas deste PDF.")
