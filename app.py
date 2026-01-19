import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="AM CRM", layout="wide")
st.markdown("<style>header, footer, #MainMenu {visibility: hidden !important;}</style>", unsafe_allow_html=True)

DB_NAME = "am_v2026_lotes.db"

# --- 2. BANCO DE DADOS (ABRE/FECHA RÁPIDO) ---
def execute_db(query, params=()):
    with sqlite3.connect(DB_NAME, timeout=10) as conn:
        conn.execute(query, params)
        conn.commit()

def query_db(query, params=()):
    with sqlite3.connect(DB_NAME, timeout=10) as conn:
        return pd.read_sql(query, conn, params=params)

# Tabelas com coluna 'lote' para exclusão em massa
execute_db("""CREATE TABLE IF NOT EXISTS historico (
    id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, 
    produto TEXT, qtde REAL, preco REAL, data TEXT, lote TEXT)""")

execute_db("""CREATE TABLE IF NOT EXISTS jornal (
    id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, produto TEXT, 
    preco_oferta REAL, validade TEXT, lote TEXT)""")

# --- 3. MOTOR DE EXTRAÇÃO ---
def extrair_pdf(file):
    lista = []
    cli, fon = "Cliente", ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            txt = page.extract_text()
            if not txt: continue
            if cli == "Cliente":
                m_c = re.search(r"Nome Fantasia:\s*(.*)", txt)
                if m_c: cli = m_c.group(1).split('\n')[0].strip()
                m_f = re.search(r"Fone:\s*(\d+)", txt)
                if m_f: fon = m_f.group(1).strip()
            for l in txt.split("\n"):
                if re.match(r"^\d{4,7}\s+", l):
                    pts = l.split()
