import sqlite3
import pdfplumber
import re
from datetime import datetime

DB = "crm.db"

# ================= CONEXAO =================

def conectar():
    return sqlite3.connect(DB)

# ================= BANCO AUTO-REPARAVEL =================

def preparar_banco():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS CLIENTES (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT,
        nome TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS PEDIDOS (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER,
        data TEXT,
        codigo_prod TEXT,
        nome_prod TEXT,
        qtde REAL,
        preco_unit REAL,
        valor_total REAL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS OFERTAS (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_prod TEXT,
        nome_prod TEXT,
        preco_pr REAL,
        validade TEXT,
        edicao TEXT
    )
    """)

    cur.execute("PRAGMA table_info(CLIENTES)")
    colunas = [c[1] for c in cur.fetchall()]

    if "codigo" not in colunas or "nome" not in colunas:
        cur.execute("ALTER TABLE CLIENTES RENAME TO CLIENTES_OLD")

        cur.execute("""
        CREATE TABLE CLIENTES (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT,
            nome TEXT
        )
        """)

        cur.execute("""
        INSERT INTO CLIENTES (codigo, nome)
        SELECT
            COALESCE(codigo, 'DESCONHECIDO'),
            COALESCE(nome, 'CLIENTE NAO IDENTIFICADO')
        FROM CLIENTES_OLD
        """)

        cur.execute("DROP TABLE CLIENTES_OLD")

    conn.commit()
    conn.close()

# ================= UTIL =================

def normalizar_preco(txt):
    return float(txt.replace(".", "").replace(",", "."))

# ==========
