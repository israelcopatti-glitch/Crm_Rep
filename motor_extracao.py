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

    # cria tabelas base
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

    # verifica estrutura real da tabela CLIENTES
    cur.execute("PRAGMA table_info(CLIENTES)")
    colunas = [c[1] for c in cur.fetchall()]

    # se banco antigo, reconstrói automaticamente
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

# ================= JORNAL =================

def extrair_jornal(pdf_path, validade, edicao):
    preparar_banco()

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
    preparar_banco()

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
                normalizar_preco(m.group(5))
            ))

    return cliente, data, itens

# ================= SALVAR =================

def salvar_pedido(cliente, data, itens):
    preparar_banco()
    conn = conectar()
    cur = conn.cursor()

    codigo = cliente.get("codigo", "DESCONHECIDO")
    nome = cliente.get("nome", "CLIENTE NAO IDENTIFICADO")

    cur.execute(
        "INSERT INTO CLIENTES (codigo,nome) VALUES (?,?)",
        (codigo, nome)
    )
    cliente_id = cur.lastrowid

    for codigo_prod, nome_prod, qtde, unit, total in itens:
        cur.execute("""
            INSERT INTO PEDIDOS
            (cliente_id,data,codigo_prod,nome_prod,qtde,preco_unit,valor_total)
            VALUES (?,?,?,?,?,?,?)
        """, (cliente_id, data, codigo_prod, nome_prod, qtde, unit, total))

    conn.commit()
    conn.close()

def salvar_ofertas(ofertas):
    preparar_banco()
    conn = conectar()
    cur = conn.cursor()

    cur.executemany("""
        INSERT INTO OFERTAS
        (codigo_prod,nome_prod,preco_pr,validade,edicao)
        VALUES (?,?,?,?,?)
    """, ofertas)

    conn.commit()
    conn.close()

preparar_banco()
