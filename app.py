import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
from fpdf import FPDF
import urllib.parse
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime, timedelta

# ---------------------------
# BANCO DE DADOS (SQLite) - Persistência Total
# ---------------------------
conn = sqlite3.connect("crm.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    cnpj TEXT UNIQUE,
    telefone TEXT
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER,
    produto TEXT,
    sku TEXT,
    quantidade REAL,
    preco_unit REAL,
    preco_total REAL,
    data TEXT,
    FOREIGN KEY(cliente_id) REFERENCES clientes(id)
);
""")
conn.commit()

# ---------------------------
# FUNÇÕES DE APOIO
# ---------------------------
def extrair_dados_pdf_depecil(arquivo):
    dados = []
    with pdfplumber.open(arquivo) as pdf:
        texto_completo = ""
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"
        
        # Pega Nome e Fone do cabeçalho
        nome_fantasia = "Cliente"
        match_nome = re.search(r"Nome Fantasia:\s*(.*)", texto_completo)
        if match_nome: nome_fantasia = match_nome.group(1).split('\n')[0].strip()
        
        match_fone = re.search(r"Fone:\s*([\d\s\-]+)", texto_completo)
        fone = "".join(re.findall(r'\d+', match_fone.group(1))) if match_fone else ""

        linhas = texto_completo.split("\n")
        for linha in linhas:
            partes = linha.split()
            if len(partes) >= 5 and partes[0].isdigit():
                sku = partes[0]
                # Pega o penúltimo valor (preço unitário no padrão Depecil)
                try:
                    p_unit = float(partes[-2].replace(".", "").replace(",", "."))
                    p_total = float(partes[-1].replace(".", "").replace(",", "."))
                    nome_prod = " ".join(partes[1:-5])
                    dados.append({
                        "produto": nome_prod, "sku": sku,
                        "preco_unit": p_unit, "preco_total": p_total
                    })
                except: continue
    return pd.DataFrame(dados), nome_fantasia, fone

# ---------------------------
# INTERFACE STREAMLIT
# ---------------------------
st.set_page_config(page_title="AM CRM Profissional", layout="wide")
st.title("📦 CRM AM Representações - Versão Full")

menu = st.sidebar.selectbox("Navegação", [
    "📥 Importar Pedido",
    "🔥 Comparar Ofertas",
    "📊 Relatórios & Vendas",
    "👥 Meus Clientes",
    "⚠️ Alertas (Inativos)"
])

# ---------------------------
# 1) IMPORTAR PEDIDO
# ---------------------------
if menu == "Importar Pedido":
    st.header("📄 Importar Pedido PDF")
    arquivo_pdf = st.file_uploader("Carregar PDF do pedido (Depecil/Toderke)", type=["pdf"])

    if arquivo_pdf:
        df, nome_cliente, fone = extrair_dados_pdf_depecil(arquivo_pdf)
        st.write(f"**Cliente Identificado:** {nome_cliente}")
        st.dataframe(df)

        if st.button("Confirmar e Salvar no Banco"):
            # Cria ou busca cliente
            cursor.execute("INSERT OR IGNORE INTO clientes (nome, cnpj, telefone) VALUES (?, ?, ?)", 
                           (nome_cliente, "000", fone))
            cursor.execute("SELECT id FROM clientes WHERE nome = ?", (nome_cliente,))
            cliente_id = cursor.fetchone()[0]

            for _, row in df.iterrows():
                cursor.execute("""
                INSERT INTO pedidos (cliente_id, produto, sku, quantidade, preco_unit, preco_total, data)
                VALUES (?, ?, ?, ?, ?, ?, DATE('now'))
                """, (cliente_id, row["produto"], row["sku"], 1, row["preco_unit"], row["preco_total"]))
            conn.commit()
            st.success("✅ Histórico atualizado com sucesso!")
            st.balloons()

# ---------------------------
# 3) RELATÓRIOS AVANÇADOS
# ---------------------------
elif menu == "Relatórios & Vendas":
    st.header("📈 Relatórios de Desempenho")
    df_pedidos = pd.read_sql_query("""
        SELECT p.*, c.nome as cliente_nome 
        FROM pedidos p JOIN clientes c ON p.cliente_id = c.id
    """, conn)

    if not df_pedidos.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Top 5 Clientes")
            vendas_cli = df_pedidos.groupby("cliente_nome")["preco_total"].sum().nlargest(5)
            st.bar_chart(vendas_cli)
        
        with col2:
            st.subheader("Produtos + Vendidos")
            vendas_prod = df_pedidos.groupby("produto")["quantidade"].sum().nlargest(5)
            st.bar_chart(vendas_prod)

        st.subheader("Lista Geral de Pedidos")
        st.dataframe(df_pedidos)

# ---------------------------
# 5) ALERTAS DE INATIVOS
# ---------------------------
elif menu == "Alertas (Inativos)":
    st.header("⚠️ Clientes sem comprar")
    dias = st.slider("Dias de inatividade:", 15, 90, 30)
    
    query = f"""
    SELECT c.nome, MAX(p.data) as ultima_compra, c.telefone
    FROM clientes c
    JOIN pedidos p ON c.id = p.cliente_id
    GROUP BY c.nome
    HAVING ultima_compra <= DATE('now', '-{dias} days')
    """
    inativos = pd.read_sql_query(query, conn)
    
    if not inativos.empty:
        st.warning(f"Encontramos {len(inativos)} clientes sumidos há mais de {dias} dias!")
        st.dataframe(inativos)
    else:
        st.success("Todos os clientes estão ativos!")
