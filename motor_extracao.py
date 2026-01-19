import sqlite3
import pdfplumber
import re
from datetime import datetime

DB = "crm.db"

# ================= CONEXAO =================

def conectar():
    return sqlite3.connect(DB)

# ================= AUTO-CORRECAO BANCO =================

def garantir_coluna(cur, tabela, coluna, tipo):
    cur.execute(f"PRAGMA table_info({tabela})")
    colunas = [c[1] for c in cur.fetchall()]
    if coluna not in colunas:
        cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")

def preparar_banco():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS CLIENTES (
        id INTEGER PRIMARY KEY AUTOINCREMENT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS PEDIDOS (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS OFERTAS (
        id INTEGER PRIMARY KEY AUTOINCREMENT
    )
    """)

    garantir_coluna(cur, "CLIENTES", "codigo", "TEXT")
    garantir_coluna(cur, "CLIENTES", "nome", "TEXT")

    garantir_coluna(cur, "PEDIDOS", "cliente_id", "INTEGER")
    garantir_coluna(cur, "PEDIDOS", "data", "TEXT")
    garantir_coluna(cur, "PEDIDOS", "codigo_prod", "TEXT")
    garantir_coluna(cur, "PEDIDOS", "nome_prod", "TEXT")
    garantir_coluna(cur, "PEDIDOS", "qtde", "REAL")
    garantir_coluna(cur, "PEDIDOS", "preco_unit", "REAL")
    garantir_coluna(cur, "PEDIDOS", "valor_total", "REAL")

    garantir_coluna(cur, "OFERTAS", "codigo_prod", "TEXT")
    garantir_coluna(cur, "OFERTAS", "nome_prod", "TEXT")
    garantir_coluna(cur, "OFERTAS", "preco_pr", "REAL")
    garantir_coluna(cur, "OFERTAS", "validade", "TEXT")
    garantir_coluna(cur, "OFERTAS", "edicao", "TEXT")

    conn.commit()
    conn.close()

# ================= UTIL =================

def normalizar_preco(txt):
    return float(txt.replace(".", "").replace(",", "."))

# ================= JORNAL =================

def extrair_jornal(pdf_path, validade, edicao):
    with pdfplumber.open(pdf_path) as pdf:
        texto = pdf.pages[0].extract_text()

    if "R$ SC" in texto and "R$ PR" in texto:
        return extrair_jornal_tabela(pdf_path, validade, edicao)
    elif "R$ PR" in texto:
        return extrair_jornal_bloco_pr(pdf_path, validade, edicao)
    else:
        raise Exception("Formato de jornal nao reconhecido")

def extrair_jornal_bloco_pr(pdf_path, validade, edicao):
    ofertas = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            texto = page.extract_text()
            if not texto:
                continue
            linhas = [l.strip() for l in texto.split("\n") if l.strip()]
            nome_atual = None
            modo_pr = False

            for linha in linhas:
                if linha.isupper() and len(linha) > 5:
                    nome_atual = linha
                    modo_pr = False
                elif linha == "R$ PR":
                    modo_pr = True
                elif modo_pr:
                    m = re.search(r"^(\d+).*?(\d+,\d+)$", linha)
                    if m and nome_atual:
                        ofertas.append((
                            m.group(1),
                            nome_atual,
                            normalizar_preco(m.group(2)),
                            validade,
                            edicao
                        ))
                        modo_pr = False
    return ofertas

def extrair_jornal_tabela(pdf_path, validade, edicao):
    ofertas = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            texto = page.extract_text()
            if not texto:
                continue
            linhas = [l.strip() for l in texto.split("\n") if l.strip()]
            nome_atual = None

            for linha in linhas:
                if linha.isupper() and not linha.startswith("R$"):
                    nome_atual = linha
                elif re.match(r"^\d+", linha) and nome_atual:
                    partes = linha.split()
                    if len(partes) >= 6:
                        ofertas.append((
                            partes[0],
                            nome_atual,
                            normalizar_preco(partes[-2]),
                            validade,
                            edicao
                        ))
    return ofertas

# ================= PEDIDO =================

def extrair_pedido(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        texto = "\n".join(p.extract_text() for p in pdf.pages if p.extract_text())

    cliente = {}
    itens = []

    m = re.search(r"(\d+)\s-\s(.+?)\s+Nº Pedido", texto)
    if m:
        cliente["codigo"] = m.group(1)
        cliente["nome"] = m.group(2).strip()

    m = re.search(r"Data Emissão:\s(\d{2}/\d{2}/\d{4})", texto)
    data = datetime.strptime(m.group(1), "%d/%m/%Y").date().isoformat()

    for linha in texto.split("\n"):
        m = re.match(
            r"^(\d+)\s+(.+?)\s+PC\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)",
            linha
        )
        if m:
            itens.append((
                m.group(1),
                m.group(2).strip(),
                normalizar_preco(m.group(3)),
                normalizar_preco(m.group(4)),
