import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
import urllib.parse
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="AM CRM Profissional", layout="wide")

# --- BANCO DE DADOS (SQLite) ---
conn = sqlite3.connect("crm_vendas.db", check_same_thread=False)
cursor = conn.cursor()

# Tabela de Histórico (6 meses)
cursor.execute("""
CREATE TABLE IF NOT EXISTS historico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente TEXT, fone TEXT, sku TEXT, produto TEXT, preco REAL, data TEXT
)""")

# Tabela de Jornal com Validade
cursor.execute("""
CREATE TABLE IF NOT EXISTS jornal_atual (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT, produto_jornal TEXT, preco_oferta REAL, data_vencimento TEXT
)""")
conn.commit()

# --- FUNÇÕES DE LIMPEZA ---
def limpar_jornal_vencido():
    hoje = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("DELETE FROM jornal_atual WHERE data_vencimento < ?", (hoje,))
    conn.commit()

# --- MOTORES DE LEITURA ---
def ler_pedido_depecil(arquivo):
    dados = []
    with pdfplumber.open(arquivo) as pdf:
        texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    
    cliente = re.search(r"Nome Fantasia:\s*(.*)", texto)
    cliente = cliente.group(1).split('\n')[0].strip() if cliente else "Cliente"
    fone = re.search(r"Fone:\s*([\d\s\-]+)", texto)
    fone = "".join(re.findall(r'\d+', fone.group(1))) if fone else ""
    if fone and not fone.startswith("55"): fone = "55" + fone

    for linha in texto.split("\n"):
        partes = linha.split()
        if len(partes) >= 6 and partes[0].isdigit():
            sku = partes[0]
            precos = [p for p in partes if "," in p]
            if len(precos) >= 2:
                try:
                    p_unit = float(precos[-2].replace(".", "").replace(",", "."))
                    nome_prod = " ".join(partes[1:partes.index(precos[0])])
                    dados.append({"sku": sku, "produto": nome_prod, "preco": p_unit, "cliente": cliente, "fone": fone})
                except: continue
    return pd.DataFrame(dados)

def ler_jornal_pdf(arquivo, dias_validade):
    limpar_jornal_vencido() # Limpa antes de inserir novo
    vencimento = (datetime.now() + timedelta(days=dias_validade)).strftime("%Y-%m-%d")
    
    with pdfplumber.open(arquivo) as pdf:
        texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    
    itens = re.findall(r"(\d{1,6})\s+(.*?)\s+.*?([\d,]{2,})$", texto, re.MULTILINE)
    for sku, prod, preco in itens:
        preco_f = float(preco.replace('.', '').replace(',', '.'))
        cursor.execute("INSERT INTO jornal_atual (sku, produto_jornal, preco_oferta, data_vencimento) VALUES (?,?,?,?)",
                       (sku, prod.strip(), preco_f, vencimento))
    conn.commit()

# --- INTERFACE ---
limpar_jornal_vencido() # Garante que o app inicie sem ofertas vencidas
st.title("🚀 AM Representações - CRM Inteligente")

menu = st.sidebar.selectbox("Menu Principal", [
    "📥 Importar Pedido", 
    "📰 Importar Jornal", 
    "🔥 Cruzamento de Ofertas", 
    "👥 Clientes & Histórico", 
    "📈 Relatórios",
    "⚠️ Clientes Inativos"
])

# 1) IMPORTAR PEDIDO
if menu == "📥 Importar Pedido":
    st.header("Importar Pedido PDF")
    arq = st.file_uploader("Suba o pedido (Depecil)", type="pdf")
    if arq:
        df = ler_pedido_depecil(arq)
        if not df.empty:
            st.success(f"✅ Pedido: {df['cliente'].iloc[0]}")
            st.dataframe(df[['sku', 'produto', 'preco']])
            if st.button("Salvar no Histórico"):
                for _, r in df.iterrows():
                    cursor.execute("INSERT INTO historico (cliente, fone, sku, produto, preco, data) VALUES (?,?,?,?,?,?)",
                                   (r['cliente'], r['fone'], r['sku'], r['produto'], r['preco'], datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
                st.balloons()

# 2) IMPORTAR JORNAL
elif menu == "📰 Importar Jornal":
    st.header("Importar Jornal de Ofertas")
    validade = st.number_input("O jornal é válido por quantos dias?", min_value=1, max_value=30, value=7)
    arq_j = st.file_uploader("Suba o Jornal PDF", type="pdf")
    if arq_j:
        if st.button("Processar e Ativar Ofertas"):
            ler_jornal_pdf(arq_j, validade)
            st.success(f"✅ Jornal importado! As ofertas expiram em {validade} dias.")

# 3) CRUZAMENTO DE OFERTAS
elif menu == "🔥 Cruzamento de Ofertas":
    st.header("Cruzamento Inteligente")
    df_j = pd.read_sql("SELECT * FROM jornal_atual", conn)
    df_h = pd.read_sql("SELECT * FROM historico", conn)
    
    if not df_j.empty and not df_h.empty:
        cruzado = pd.merge(df_j, df_h, on="sku")
        ofertas = cruzado[cruzado['preco_oferta'] < cruzado['preco']].drop_duplicates(subset=['sku', 'cliente'])
        
        if not ofertas.empty:
            cliente_sel = st.selectbox("Selecione o Cliente:", ofertas['cliente'].unique())
            df_envio = ofertas[ofertas['cliente'] == cliente_sel]
            
            st.write(f"### 🔥 {len(df_envio)} Ofertas encontradas!")
            st.table(df_envio[['produto_jornal', 'preco', 'preco_oferta']])
            
            msg = f"Olá, *{cliente_sel}*! 👋 Itens que você comprou baixaram de preço:\n\n"
            for _, r in df_envio.iterrows():
                msg += f"✅ *{r['produto_jornal']}*\nDe: R${r['preco']:.2f} por *R${r['preco_oferta']:.2f}*\n\n"
            
            link = f"https://wa.me/{df_envio['fone'].iloc[0]}?text={urllib.parse.quote(msg)}"
            st.markdown(f"## [👉 ENVIAR PARA O WHATSAPP REAL]({link})")
        else:
            st.info("Nenhuma oferta atual é menor que o preço pago no histórico.")
    else:
        st.warning("Certifique-se de ter um Jornal Ativo e um Histórico populado.")

# 4) RELATÓRIOS
elif menu == "📈 Relatórios":
    st
