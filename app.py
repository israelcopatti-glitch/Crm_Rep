import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from fpdf import FPDF
import urllib.parse
import os
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="AM Representações CRM", layout="wide")

# --- BANCO DE DADOS (SQLite) ---
conn = sqlite3.connect("crm.db", check_same_thread=False)
cursor = conn.cursor()

# Criação das tabelas se não existirem
cursor.execute("CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, cnpj TEXT UNIQUE, telefone TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS pedidos (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER, produto TEXT, sku TEXT, quantidade REAL, preco_unit REAL, preco_total REAL, data TEXT, FOREIGN KEY(cliente_id) REFERENCES clientes(id))")
conn.commit()

# --- MOTORES DE LEITURA (PDF) ---
def extrair_dados_pdf_pedido(arquivo):
    with pdfplumber.open(arquivo) as pdf:
        texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    
    # Busca Nome e Telefone
    cliente = re.search(r"Nome Fantasia:\s*(.*)", texto)
    cliente = cliente.group(1).split('\n')[0].strip() if cliente else "Cliente Avulso"
    fone = re.search(r"Fone:\s*([\d\s\-]+)", texto)
    fone = "".join(re.findall(r'\d+', fone.group(1))) if fone else ""
    if fone and not fone.startswith("55"): fone = "55" + fone

    dados = []
    for linha in texto.split("\n"):
        partes = linha.split()
        if len(partes) >= 6 and partes[0].isdigit():
            sku = partes[0]
            precos = [p for p in partes if "," in p]
            if len(precos) >= 2:
                try:
                    p_unit = float(precos[-2].replace(".", "").replace(",", "."))
                    nome_prod = " ".join(partes[1:partes.index(precos[0])])
                    dados.append({"Produto": nome_prod, "SKU": sku, "Preço": p_unit, "Cliente": cliente, "Telefone": fone})
                except: continue
    return pd.DataFrame(dados)

def extrair_dados_jornal(arquivo):
    with pdfplumber.open(arquivo) as pdf:
        texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    # Padrão flexível para o jornal de ofertas
    itens = re.findall(r"(\d{1,6})\s+(.*?)\s+.*?([\d,]{2,})$", texto, re.MULTILINE)
    df = pd.DataFrame(itens, columns=['SKU', 'Produto_Jornal', 'Preço_Oferta'])
    df['Preço_Oferta'] = df['Preço_Oferta'].str.replace('.', '').str.replace(',', '.').astype(float)
    df['SKU'] = df['SKU'].astype(str).str.strip()
    return df

# --- INTERFACE ---
st.title("🚀 AM Representações - CRM Completo")

menu = st.sidebar.selectbox("Escolha uma Opção:", [
    "📥 Importar Pedido (PDF)",
    "🔥 Jornal de Ofertas (Comparar)",
    "👥 Base de Clientes & Histórico",
    "📈 Relatórios & Estatísticas",
    "⚠️ Alertas de Inatividade"
])

# 1) IMPORTAR PEDIDO
if menu == "📥 Importar Pedido (PDF)":
    st.header("📄 Adicionar Novo Pedido ao Histórico")
    arquivo_pdf = st.file_uploader("Suba o PDF do Pedido", type=["pdf"])
    if arquivo_pdf:
        df = extrair_dados_pdf_pedido(arquivo_pdf)
        if not df.empty:
            st.success(f"✅ Pedido identificado: {df['Cliente'].iloc[0]}")
            st.dataframe(df)
            if st.button("💾 Salvar no Banco de Dados (6 Meses)"):
                cursor.execute("INSERT OR IGNORE INTO clientes (nome, cnpj, telefone) VALUES (?, ?, ?)", (df['Cliente'].iloc[0], "000", df['Telefone'].iloc[0]))
                cursor.execute("SELECT id FROM clientes WHERE nome = ?", (df['Cliente'].iloc[0],))
                c_id = cursor.fetchone()[0]
                for _, r in df.iterrows():
                    cursor.execute("INSERT INTO pedidos (cliente_id, produto, sku, preco_unit, data) VALUES (?, ?, ?, ?, DATE('now'))", (c_id, r['Produto'], r['SKU'], r['Preço']))
                conn.commit()
                st.success("Dados salvos com sucesso!")
        else: st.error("Não foi possível ler os itens.")

# 2) JORNAL DE OFERTAS
elif menu == "🔥 Jornal de Ofertas (Comparar)":
    st.header("💰 Comparar Jornal com Preços Pagos")
    arquivo_jornal = st.file_uploader("Suba o PDF do Jornal de Ofertas", type=["pdf"])
    if arquivo_jornal:
        df_jornal = extrair_dados_jornal(arquivo_jornal)
        # Busca todo o histórico do banco
        df_hist = pd.read_sql_query("SELECT p.sku, p.produto, p.preco_unit as Preco_Antigo, c.nome, c.telefone FROM pedidos p JOIN clientes c ON p.cliente_id = c.id", conn)
        
        if not df_hist.empty:
            cruzado = pd.merge(df_jornal, df_hist, left_on="SKU", right_on="sku")
            ofertas = cruzado[cruzado['Preço_Oferta'] < cruzado['Preco_Antigo']].drop_duplicates(subset=['SKU', 'nome'])
            
            if not ofertas.empty:
                st.write(f"### 🔥 Encontramos {len(ofertas)} itens mais baratos!")
                st.dataframe(ofertas[['nome', 'Produto_Jornal', 'Preco_Antigo', 'Preço_Oferta']])
                
                cliente_sel = st.selectbox("Enviar ofertas para qual cliente?", ofertas['nome'].unique())
                df_envio = ofertas[ofertas['nome'] == cliente_sel]
                
                msg = f"Olá, *{cliente_sel}*! 👋 Itens que você já comprou estão em promoção:\n\n"
                for _, r in df_envio.iterrows():
                    msg += f"✅ *{r['Produto_Jornal']}*\nDe: R${r['Preco_Antigo']:.2f} por *R${r['Preço_Oferta']:.2f}*\n\n"
                
                link = f"https://wa.me/{df_envio['telefone'].iloc[0]}?text={urllib.parse.quote(msg)}"
                st.markdown(f"## [👉 ENVIAR WHATSAPP PARA {cliente_sel}]({link})")
            else: st.info("Nenhuma oferta menor que o histórico encontrada.")

# 3) BASE DE CLIENTES & HISTÓRICO
elif menu == "👥 Base de Clientes & Histórico":
    st.header("👥 Meus Clientes e Compras")
    df_cli = pd.read_sql_query("SELECT id, nome, telefone FROM clientes", conn)
    if not df_cli.empty:
        cliente_id = st.selectbox("Selecione o Cliente:", df_cli['nome'].tolist())
        id_real = df_cli[df_cli['nome'] == cliente_id]['id'].iloc[0]
        
        st.subheader(f"Histórico de {cliente_id}")
        df_ped = pd.read_sql_query(f"SELECT data as Data, sku as SKU, produto as Produto, preco_unit as Preço FROM pedidos WHERE cliente_id = {id_real} ORDER BY data DESC", conn)
        st.dataframe(df_ped)
    else: st.info("Nenhum cliente no banco de dados.")

# 4) RELATÓRIOS & ESTATÍSTICAS
elif menu == "📈 Relatórios & Estatísticas":
    st.header("📈 Estatísticas Gerais")
    df_vendas = pd.read_sql_query("SELECT p.produto, SUM(p.preco_unit) as Total FROM
