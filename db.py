import sqlite3

# Conexão com o banco de dados
conn = sqlite3.connect("crm.db", check_same_thread=False)
cur = conn.cursor()

# Criando as tabelas, caso não existam
cur.execute('''
CREATE TABLE IF NOT EXISTS CLIENTES (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT,
    nome TEXT
)
''')

cur.execute('''
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
''')

cur.execute('''
CREATE TABLE IF NOT EXISTS OFERTAS (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_prod TEXT,
    nome_prod TEXT,
    preco_pr REAL,
    validade TEXT,
    edicao TEXT
)
''')

# Função para inserir ou atualizar cliente
def inserir_cliente(cliente):
    cur.execute('''
    INSERT OR REPLACE INTO CLIENTES (codigo, nome)
    VALUES (?, ?)
    ''', (cliente["codigo"], cliente["nome"]))
    conn.commit()

# Função para inserir pedidos
def inserir_pedido(cliente_id, pedidos):
    for pedido in pedidos:
        cur.execute('''
        INSERT INTO PEDIDOS (cliente_id, data, codigo_prod, nome_prod, qtde, preco_unit, valor_total)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (cliente_id, pedido["data"], pedido["codigo"], pedido["nome"], pedido["qtde"], pedido["preco"], pedido["total"]))
    conn.commit()

# Função para verificar se o cliente já existe
def buscar_cliente_por_codigo(codigo_cliente):
    cur.execute('''
    SELECT id, nome FROM CLIENTES WHERE codigo = ?
    ''', (codigo_cliente,))
    return cur.fetchone()

# Fechar a conexão
def fechar_conexao():
    conn.close()
