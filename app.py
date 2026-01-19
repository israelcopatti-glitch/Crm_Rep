import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
from datetime import datetime

# =========================================================
# CONFIGURAÇÃO INICIAL DO STREAMLIT
# =========================================================
st.set_page_config(
    page_title="CRM Comercial | MVP",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# INICIALIZAR BANCO DE DADOS SQLITE
# =========================================================
def init_db():
    conn = sqlite3.connect("crm.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        cnpj TEXT UNIQUE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pedidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER,
        data DATE,
        codigo TEXT,
        produto TEXT,
        qtd INTEGER,
        preco_unit REAL,
        preco_total REAL,
        FOREIGN KEY(cliente_id) REFERENCES clientes(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ofertas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT,
        produto TEXT,
        preco_pr REAL,
        data_inicio DATE,
        data_fim DATE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alertas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER,
        codigo TEXT,
        mensagem TEXT,
        data DATE,
        FOREIGN KEY(cliente_id) REFERENCES clientes(id)
    )
    """)

    conn.commit()
    conn.close()

init_db()

# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================
def adicionar_cliente(nome, cnpj):
    conn = sqlite3.connect("crm.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO clientes (nome, cnpj) VALUES (?,?)", (nome, cnpj))
        conn.commit()
    except:
        pass
    conn.close()

def buscar_cliente_por_cnpj(cnpj):
    conn = sqlite3.connect("crm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM clientes WHERE cnpj = ?", (cnpj,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def salvar_pedido(cliente_id, codigo, produto, qtd, preco_unit, preco_total):
    conn = sqlite3.connect("crm.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO pedidos (cliente_id, data, codigo, produto, qtd, preco_unit, preco_total)
        VALUES (?,?,?,?,?,?,?)
    """, (cliente_id, datetime.now().date(), codigo, produto, qtd, preco_unit, preco_total))
    conn.commit()
    conn.close()

# =========================================================
# EXTRAÇÃO SIMPLES DO PDF (PLACEHOLDER)
# =========================================================
def extrair_pedido_simples(pdf_file):
    """
    Essa função lê o PDF e retorna um exemplo.
    Depois vamos substituir pela extração real OCR/Regex.
    """
    example = [
        {"CNPJ": "12.345.678/0001-90", "Cliente": "Cliente Exemplo",
         "Código": "37050", "Produto": "DOBRADICA SOBREPOR",
         "Qtd": 60, "Unit": 31.62, "Total": 1897.42}
    ]
    return pd.DataFrame(example)

# =========================================================
# PÁGINA: HOME
# =========================================================
def pagina_home():
    st.title("📦 CRM Comercial - MVP")
    st.subheader("Análise de Pedidos & Ofertas - Mobile Ready")
    st.write("""
        Bem-vindo ao MVP!  
        Aqui você poderá extrair pedidos de PDF, importar ofertas e gerar alertas automáticos.
    """)
    st.success("💡 Totalmente funcional via celular!")

# =========================================================
# PÁGINA: IMPORTAR PEDIDOS PDF
# =========================================================
def pagina_importar_pedidos():
    st.title("📄 Importar Pedidos (PDF)")

    pdf_file = st.file_uploader("Selecione o PDF do pedido", type=["pdf"])

    if pdf_file:
        st.info("📁 Processando PDF...")

        df = extrair_pedido_simples(pdf_file)
        st.dataframe(df)

        if st.button("Salvar Pedido no Sistema"):
            cnpj = df.iloc[0]["CNPJ"]
            cliente = df.iloc[0]["Cliente"]

            adicionar_cliente(cliente, cnpj)
            cliente_id = buscar_cliente_por_cnpj(cnpj)

            for _, row in df.iterrows():
                salvar_pedido(
                    cliente_id,
                    row["Código"],
                    row["Produto"],
                    row["Qtd"],
                    row["Unit"],
                    row["Total"]
                )
            st.success("✔ Pedido salvo com sucesso!")

# =========================================================
# PÁGINA: IMPORTAR OFERTAS (JORNAL)
# =========================================================
def pagina_ofertas():
    st.title("📰 Importar Jornal de Ofertas")

    excel = st.file_uploader("Selecione arquivo XLSX/CSV", type=["xlsx", "csv"])

    if excel:
        if excel.name.endswith(".csv"):
            df = pd.read_csv(excel)
        else:
            df = pd.read_excel(excel)

        st.dataframe(df)

        if st.button("Salvar Ofertas"):
            conn = sqlite3.connect("crm.db")
            cursor = conn.cursor()
            for _, row in df.iterrows():
                cursor.execute("""
                    INSERT INTO ofertas (codigo, produto, preco_pr, data_inicio, data_fim)
                    VALUES (?,?,?,?,?)
                """, (row["Código"], row["Produto"], row["PR"], datetime.now().date(), None))
            conn.commit()
            conn.close()
            st.success("✔ Ofertas salvas com sucesso!")

# =========================================================
# PÁGINA: RELATÓRIOS
# =========================================================
def pagina_relatorios():
    st.title("📊 Relatórios e Indicadores")

    conn = sqlite3.connect("crm.db")
    df = pd.read_sql_query("""
        SELECT c.nome, p.codigo, p.produto, SUM(p.qtd) as total_qtd, SUM(p.preco_total) as total_vendido
        FROM pedidos p
        JOIN clientes c ON p.cliente_id = c.id
        GROUP BY c.nome, p.codigo, p.produto
    """, conn)
    conn.close()

    if df.empty:
        st.warning("Sem dados ainda! Importe pedidos primeiro.")
        return

    st.subheader("🔥 Produtos mais vendidos")
    st.dataframe(df.sort_values("total_qtd", ascending=False).head(10))

    st.subheader("💰 Melhores clientes por faturamento")
    clientes = df.groupby("nome")["total_vendido"].sum().reset_index()
    st.dataframe(clientes.sort_values("total_vendido", ascending=False).head(10))

# =========================================================
# SISTEMA DE NAVEGAÇÃO
# =========================================================
menu = st.sidebar.radio("Menu", [
    "🏠 Home",
    "📄 Importar Pedidos",
    "📰 Importar Ofertas",
    "📊 Relatórios"
])

if menu == "🏠 Home":
    pagina_home()

elif menu == "📄 Importar Pedidos":
    pagina_importar_pedidos()

elif menu == "📰 Importar Ofertas":
    pagina_ofertas()

elif menu == "📊 Relatórios":
    pagina_relatorios()
