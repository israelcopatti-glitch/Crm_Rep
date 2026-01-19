import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
import urllib.parse
from datetime import datetime, timedelta

# --- BLOQUEIO TOTAL DE INTERFACE (ANTI-STREAMLIT) ---
st.set_page_config(page_title="AM CRM", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    /* Esconde barra superior, rodapé e menu de gestão */
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    header {visibility: hidden !important;}
    .stDeployButton {display:none !important;}
    [data-testid="managed_by_streamlit"] {display: none !important;}
    [data-testid="stStatusWidget"] {display: none !important;}
    #stDecoration {display:none !important;}
    .viewerBadge_container__1QSob {display: none !important;}
    .st-emotion-cache-zq5wmm {display: none !important;} /* Esconde barra de ferramentas */
    </style>
""", unsafe_allow_html=True)

# --- BANCO DE DADOS ---
conn = sqlite3.connect("crm_am_v3.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, produto TEXT, preco REAL, data TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS jornal (sku TEXT, produto_jornal TEXT, preco_oferta REAL, vencimento TEXT)")
conn.commit()

# --- NOVO MOTOR DE LEITURA (MÉTODO DE CAPTURA POR TEXTO) ---
def ler_pdf_depecil_v3(arquivo):
    dados = []
    with pdfplumber.open(arquivo) as pdf:
        texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    
    # Captura Cliente e Fone
    cliente_match = re.search(r"Nome Fantasia:\s*(.*)", texto)
    cliente = cliente_match.group(1).split('\n')[0].strip() if cliente_match else "Cliente"
    
    fone_match = re.search(r"Fone:\s*([\d\s\-]+)", texto)
    fone = "".join(re.findall(r'\d+', fone_match.group(1))) if fone_match else ""
    if fone and not fone.startswith("55"): fone = "55" + fone

    linhas = texto.split("\n")
    for linha in linhas:
        # Tenta encontrar o padrão: Código (espaço) Nome (espaço) ... Preço
        # Ex: 37050 DOBRADICA DE SOBREPOR 3 1/2X2 5/16 CROMADO UN 1 31,6236
        match_produto = re.match(r"^(\d{1,7})\s+(.*?)\s+(\w{2})\s+\d+.*(\d+\.\d+,\d+|\d+,\d+)", linha)
        
        if match_produto:
            sku = match_produto.group(1)
            nome_prod = match_produto.group(2)
            # Limpa o nome de restos da unidade
            nome_prod = re.sub(r"\s(UN|PC|CT|RL|DZ|JG)$", "", nome_prod).strip()
            
            # Pega o preço (último ou penúltimo valor com vírgula)
            partes = linha.split()
            precos = [p for p in partes if "," in p]
            if len(precos) >= 2:
                try:
                    preco_unit = float(precos[-2].replace(".", "").replace(",", "."))
                    dados.append({"sku": sku, "produto": nome_prod, "preco": preco_unit, "cliente": cliente, "fone": fone})
                except: continue
        
        # Caso o re.match falhe, tenta a lógica de backup por SKU direto
        elif len(linha.split()) > 5 and linha.split()[0].isdigit():
            partes = linha.split()
            sku = partes[0]
            indices_virgula = [i for i, p in enumerate(partes) if "," in p]
            if indices_virgula:
                idx_fim_nome = indices_virgula[0]
                nome_prod = " ".join(partes[1:idx_fim_nome])
                try:
                    preco_unit = float(partes[-2].replace(".", "").replace(",", "."))
                    dados.append({"sku": sku, "produto": nome_prod, "preco": preco_unit, "cliente": cliente, "fone": fone})
                except: continue

    return pd.DataFrame(dados)

# --- INTERFACE ---
st.title("🚀 AM Representações")

menu = st.sidebar.selectbox("Menu:", ["📥 Importar Pedido", "📰 Jornal de Ofertas", "🔥 Cruzamento", "📊 Relatórios"])

if menu == "📥 Importar Pedido":
    st.header("Importar Pedido Depecil")
    arq = st.file_uploader("Suba o PDF", type="pdf")
    if arq:
        df = ler_pdf_depecil_v3(arq)
        if not df.empty:
            st.success(f"✅ Cliente: {df['cliente'].iloc[0]}")
            # Mostra os dados com nomes de colunas bonitos
            st.dataframe(df[['sku', 'produto', 'preco']].rename(columns={
                'sku': 'Cód/SKU', 'produto': 'Nome do Produto', 'preco': 'Preço Pago'
            }))
            
            if st.button("💾 Guardar no Histórico"):
                for _, r in df.iterrows():
                    cursor.execute("INSERT INTO historico (cliente, fone, sku, produto, preco, data) VALUES (?,?,?,?,?,?)",
                                   (r['cliente'], r['fone'], r['sku'], r['produto'], r['preco'], datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
                st.balloons()
        else:
            st.error("⚠️ O sistema leu o PDF mas não encontrou os produtos. Tenta outro ficheiro.")

# ... Resto das abas seguem o padrão ...
