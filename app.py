import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# --- 1. INTERFACE ---
st.set_page_config(page_title="AM CRM", layout="wide")
st.markdown("""<style>
    header, footer, #MainMenu, .stDeployButton {visibility: hidden; display: none !important;}
    [data-testid="stHeader"] {display: none !important;}
    .block-container {padding-top: 1rem !important;}
</style>""", unsafe_allow_html=True)

# --- 2. BANCO DE DADOS (ANTI-DUPLICIDADE) ---
def conectar():
    conn = sqlite3.connect("am_crm_vFinal_2026.db", check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, 
        produto TEXT, qtde REAL, preco REAL, data TEXT, UNIQUE(cliente, sku, data, preco))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS jornal (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, produto TEXT, 
        preco_oferta REAL, validade TEXT, UNIQUE(sku, preco_oferta, validade))""")
    return conn

db = conectar()

# --- 3. MOTOR DE LEITURA (NOME COMPLETO E FONE REAL) ---
def ler_pdf(file):
    lista = []
    cli, fon = "Cliente", ""
    with pdfplumber.open(file) as pdf:
        txt = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        m_c = re.search(r"Nome Fantasia:\s*(.*)", txt); cli = m_c.group(1).split('\n')[0].strip() if m_c else cli
        m_f = re.search(r"Fone:\s*(\d+)", txt); fon = m_f.group(1).strip() if m_f else ""
        for l in txt.split("\n"):
            if re.match(r"^\d{4,7}\s+", l):
                pts = l.split()
                v = [x for x in pts if "," in x]
                if len(v) >= 4:
                    try:
                        idx_f = pts.index(v[0])
                        lista.append({
