import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime

# --- CONFIGURAÇÃO E BLOQUEIO TOTAL DA INTERFACE ---
st.set_page_config(page_title="AM CRM", layout="wide", initial_sidebar_state="collapsed")

# CSS para esconder TUDO do Streamlit e a barra de gerenciamento
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
conn = sqlite3.connect("crm_vendas_am_final.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        cliente TEXT, sku TEXT, produto TEXT, 
        quantidade REAL, preco REAL, data TEXT
    )
""")
conn.commit()

# --- MOTOR DE EXTRAÇÃO DEPRECIL (CALIBRADO) ---
def extrair_depecil_definitivo(arquivo):
    dados = []
    cliente = "Desconhecido"
    
    with pdfplumber.open(arquivo) as pdf:
        texto_completo = ""
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"
        
        # Identifica o Nome Fantasia do Cliente
        m_cliente = re.search(r"Nome Fantasia:\s*(.*)", texto_completo)
        if m_cliente:
            cliente = m_cliente.group(1).split('\n')[0].strip()

        # Procura as linhas de produtos
        linhas = texto_completo.split("\n")
        for linha in linhas:
            # Detecta linhas que começam com o código SKU (ex: 37050)
            if re.match(r"^\d{4,6}\s+", linha):
                partes = linha
