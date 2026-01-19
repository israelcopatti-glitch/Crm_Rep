import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from fpdf import FPDF
import urllib.parse
import matplotlib.pyplot as plt
from io import BytesIO

# --- BANCO DE DADOS ---
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

# --- LEITOR DE PDF CORRIGIDO (PARA DEPECIL) ---
def extrair_dados_pdf_depecil(arquivo):
    dados = []
    nome_fantasia = "Cliente"
    fone = ""
    
    with pdfplumber.open(arquivo) as pdf:
        texto_completo = ""
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"
        
        # Busca Cabeçalho
        match_nome = re.search(r"Nome Fantasia:\s*(.*)", texto_completo)
        if match_nome: nome_fantasia = match_nome.group(1).split('\n')[0].strip()
        
        match_fone = re.search(r"Fone:\s*([\d\s\-]+)", texto_completo)
        if match_fone: fone = "".join(re.findall(r'\d+', match_fone.group(1)))

        # Busca Produtos (Lógica de colunas baseada no seu print)
        linhas = texto_completo.split("\n")
        for linha in linhas:
            partes = linha.split()
            # Se a linha começa com o código (ex: 37050)
            if len(partes) >= 6 and partes[0].isdigit():
                sku = partes[0]
                # O preço unitário na Depecil é o penúltimo ou antepenúltimo
                # Vamos buscar o valor que tem a vírgula de decimal
                precos = [p for p in partes if "," in p]
                if len(precos) >= 2:
                    p_unit = float(precos[-2].replace(".", "").replace(",", "."))
                    p_total = float(precos[-1].replace(".", "").replace(",", "."))
                    # O nome está entre o código e o primeiro preço
                    nome_prod = " ".join(partes[1:partes.index(precos[0])])
                    
                    dados.append({
                        "produto": nome_prod, 
                        "sku": sku,
                        "preco_unit": p_unit, 
                        "preco_total": p_total
                    })
    return pd.DataFrame(dados), nome_fantasia, fone

# --- INTERFACE ---
st.title("📦 CRM AM Representações - Profissional")

menu = st.sidebar.selectbox("Menu", ["Importar Pedido", "Ofertas", "Relatórios", "Clientes Inativos"])

if menu == "Importar Pedido":
    st.header("📄 Importar Pedido (Depecil)")
    arquivo_pdf = st.file_uploader("Suba o PDF", type=["pdf"])

    if arquivo_pdf:
        df, nome_cliente, fone = extrair_dados_pdf_depecil(arquivo_pdf)
        
        if not df.empty:
            st.success(f"✅ Pedido identificado: {nome_cliente}")
            st.dataframe(df)
            
            if st.button("Salvar no Banco de Dados"):
                # Salva Cliente
                cursor.execute("INSERT OR IGNORE INTO clientes (nome, cnpj, telefone) VALUES (?, ?, ?)", 
                               (nome_cliente, "000", fone))
                cursor.execute("SELECT id FROM clientes WHERE nome = ?", (nome_cliente,))
                c_id = cursor.fetchone()[0]
                
                # Salva Pedidos
                for _, row in df.iterrows():
                    cursor.execute("""
                        INSERT INTO pedidos (cliente_id, produto, sku, quantidade, preco_unit, preco_total, data)
                        VALUES (?, ?, ?, 1, ?, ?, DATE('now'))
                    """, (c_id, row['produto'], row['sku'], row['preco_unit'], row['preco_total']))
                conn.commit()
                st.success("Dados salvos! Agora você pode gerar relatórios e ofertas.")
        else:
            st.error("Não foi possível ler os itens. Verifique se o PDF é o original da Depecil.")

elif menu == "Relatórios":
    st.header("📈 Relatórios")
    df_vendas = pd.read_sql_query("""
        SELECT p.produto, SUM(p.preco_total) as Total 
        FROM pedidos p GROUP BY p.produto
    """, conn)
    if not df_vendas.empty:
        st.bar_chart(df_vendas.set_index("produto"))
    else:
        st.info("Sem dados para exibir.")

elif menu == "Clientes Inativos":
    st.header("⚠️ Alerta de Inatividade")
    # Mostra clientes que não compram há mais de 30 dias
    inativos = pd.read_sql_query("""
        SELECT c.nome, MAX(p.data) as Ultima_Compra 
        FROM clientes c JOIN pedidos p ON c.id = p.cliente_id 
        GROUP BY c.nome HAVING Ultima_Compra <= DATE('now', '-30 days')
    """, conn)
    st.table(inativos)
