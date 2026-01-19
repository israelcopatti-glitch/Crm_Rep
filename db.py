import sqlite3

conn = sqlite3.connect("crm.db", check_same_thread=False)
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

conn.commit()
