import sqlite3

def get_connection():
    return sqlite3.connect("pedidos.db", check_same_thread=False)


def init_db():
    conn = get_connection()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS pedidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente TEXT,
        telefone TEXT,
        sku TEXT,
        produto TEXT,
        valor REAL,
        lote TEXT
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS jornal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT,
        produto TEXT,
        preco_oferta REAL,
        validade TEXT,
        lote TEXT
    )""")
    conn.close()
