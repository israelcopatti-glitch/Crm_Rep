import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
import urllib.parse
from datetime import datetime

# --- BLOQUEIO TOTAL DA INTERFACE (REMOVE 'GERENCIAR APLICATIVO') ---
st.set_page_config(page_title="AM CRM", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    header {visibility: hidden !important;}
    .stDeployButton {display:none !important;}
    [data-testid="managed_by_streamlit"] {display: none !important;}
    div[data-testid="stStatusWidget"] {visibility: hidden !important;}
    #stDecoration {display:none !important;}
    .viewerBadge_container__1QSob {display: none !important;}
    </style>
""", unsafe_allow_html=True)

# --- BANCO DE DADOS ---
conn = sqlite3.connect("crm_am_final.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, produto TEXT, preco REAL, data TEXT)")
conn.commit()

# --- NOVO LEITOR CALIBRADO PARA DEPECIL ---
def ler_pdf_depecil_v5(arquivo):
    dados = []
    with pdfplumber.open(arquivo) as pdf:
        texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    
    # Busca Cliente e Fone
    cliente_match = re.search(r"Nome Fantasia:\s*(.*)", texto)
    cliente = cliente_match.group(1).split('\n')[0].strip() if cliente_match else "Cliente"
    
    fone_match = re.search(r"Fone:\s*(\d+)", texto)
    fone = fone_match.group(1) if fone_match else ""

    linhas = texto.split("\n")
    for linha in linhas:
        # Padrão: Começa com 5 dígitos, segue texto e termina com valores com vírgula
        partes = linha.split()
        if len(partes) > 6 and partes[0].isdigit() and len(partes[0]) >= 4:
            sku = partes[0]
            
            # Encontra onde começam os valores de imposto (0,00 0,00 UN...)
            # O nome do produto está entre o SKU e o primeiro "0,00" ou "UN"
            indices_valores = [i for i, p in enumerate(partes) if "," in p or p in ["UN", "PC", "CX"]]
            if indices_valores:
                idx_fim_nome = indices_valores[0]
                nome_produto = " ".join(partes[1:idx_fim_nome])
                
                # O preço unitário (V. [span_2](start_span)Unit.) é sempre o penúltimo valor da tabela[span_2](end_span)
                try:
                    # [span_3](start_span)No seu PDF o valor é 31,6236[span_3](end_span)
                    precos = [p for p in partes if "," in p]
                    preco_unit = float(precos[-2].replace(".", "").replace(",", "."))
                    
                    dados.append({
                        "Cód/SKU": sku, 
                        "Nome do Produto": nome_produto, 
                        "Preço Pago": preco_unit,
                        "Cliente": cliente,
                        "Fone": fone
                    })
                except: continue
    return pd.DataFrame(dados)

# --- INTERFACE ---
st.title("📦 AM Representações")

menu = st.sidebar.selectbox("Menu", ["📥 Importar Pedido", "🔥 Cruzamento", "📊 Relatórios"])

if menu == "📥 Importar Pedido":
    st.header("Importar Pedido Depecil")
    arq = st.file_uploader("Suba o PDF do Pedido", type="pdf")
    
    if arq:
        df = ler_pdf_depecil_v5(arq)
        if not df.empty:
            st.success(f"✅ Identificado: {df['Cliente'].iloc[0]}")
            # MOSTRA A TABELA COM O NOME CORRETO
            st.dataframe(df[["Cód/SKU", "Nome do Produto", "Preço Pago"]])
            
            if st.button("💾 Guardar no Histórico"):
                for _, r in df.iterrows():
                    cursor.execute("INSERT INTO historico (cliente, fone, sku, produto, preco, data) VALUES (?,?,?,?,?,?)",
                                   (r['Cliente'], r['Fone'], r['Cód/SKU'], r['Nome do Produto'], r['Preço Pago'], datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
                st.success("Dados salvos com sucesso!")
        else:
            st.error("⚠️ Não foi possível extrair o nome do produto. Verifique o PDF.")
