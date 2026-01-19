import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
import urllib.parse
from datetime import datetime, timedelta

# --- 1. BLOQUEIO TOTAL DE INTERFACE (MODO KIOSK) ---
st.set_page_config(page_title="AM CRM", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    /* Esconde cabeçalho, rodapé, menu e botão de gerenciar aplicativo */
    header, footer, #MainMenu {visibility: hidden !important;}
    .stDeployButton {display:none !important;}
    [data-testid="managed_by_streamlit"] {display: none !important;}
    [data-testid="stHeader"] {display: none !important;}
    #stDecoration {display:none !important;}
    .viewerBadge_container__1QSob {display:none !important;}
    button[title="View source"] {display:none !important;}
    /* Remove a barra cinza superior */
    div[data-testid="stStatusWidget"] {display: none !important;}
    </style>
""", unsafe_allow_html=True)

# --- 2. BANCO DE DADOS (Histórico de 6 meses) ---
def iniciar_banco():
    conn = sqlite3.connect("crm_am_final.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            cliente TEXT, fone TEXT, sku TEXT, produto TEXT, 
            qtde REAL, preco REAL, data TEXT
        )
    """)
    conn.commit()
    return conn

conn = iniciar_banco()

# --- 3. MOTOR DE LEITURA CALIBRADO (NOME + QUANTIDADE) ---
def extrair_dados_depecil(file):
    dados = []
    cliente, fone = "Desconhecido", ""
    with pdfplumber.open(file) as pdf:
        texto_completo = ""
        for page in pdf.pages:
            texto_completo += page.extract_text() + "\n"
        
        # Identifica Cliente e Fone
        m_cliente = re.search(r"Nome Fantasia:\s*(.*)", texto_completo)
        if m_cliente: cliente = m_cliente.group(1).split('\n')[0].strip()
        m_fone = re.search(r"Fone:\s*(\d+)", texto_completo)
        if m_fone: fone = m_fone.group(1).strip()

        linhas = texto_completo.split("\n")
        for linha in linhas:
            if
