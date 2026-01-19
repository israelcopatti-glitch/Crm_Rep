import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
import urllib.parse
from datetime import datetime, timedelta

# --- BLOQUEIO TOTAL DE INTERFACE (PARA PARECER APP REAL) ---
st.set_page_config(page_title="AM CRM", layout="wide", initial_sidebar_state="collapsed")

# CSS para esconder TUDO que indique ser Streamlit (incluindo o Gerenciar Aplicativo)
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:none;}
    div[data-testid="stStatusWidget"] {visibility: hidden;}
    #stDecoration {display:none;}
    [data-testid="managed_by_streamlit"] {display: none !important;}
    button[title="View source"], .viewerBadge_container__1QSob {display: none !important;}
    </style>
""", unsafe_allow_html=True)

# --- BANCO DE DADOS ---
conn = sqlite3.connect("crm_am.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, produto TEXT, preco REAL, data TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS jornal (sku TEXT, produto_jornal TEXT, preco_oferta REAL, vencimento TEXT)")
conn.commit()

# --- LEITOR DEPECIL CORRIGIDO (PARA PEGAR O NOME DO PRODUTO) ---
def ler_pdf_depecil_final(arquivo):
    dados = []
    with pdfplumber.open(arquivo) as pdf:
        texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    
    # Captura Cliente e Telefone (conforme sua imagem do PDF)
    cliente = re.search(r"Nome Fantasia:\s*(.*)", texto)
    cliente = cliente.group(1).split('\n')[0].strip() if cliente else "Cliente"
    fone = re.search(r"Fone:\s*([\d\s\-]+)", texto)
    fone = "".join(re.findall(r'\d+', fone.group(1))) if fone else ""
    if fone and not fone.startswith("55"): fone = "55" + fone

    linhas = texto.split("\n")
    for linha in linhas:
        partes = linha.split()
        # Se a linha começa com o SKU (ex: 37050)
        if len(partes) >= 6 and partes[0].isdigit():
            sku = partes[0]
            # Localiza onde começam os valores numéricos com vírgula (IPI, ICMS, Quantidade...)
            indices_valores = [i for i, p in enumerate(partes) if "," in p]
            if indices_valores:
                primeiro_valor_idx = indices_valores[0]
                # O Nome do Produto está ENTRE o SKU (índice 0) e o primeiro valor numérico
                nome_prod = " ".join(partes[1:primeiro_valor_idx])
                
                # O Preço Unitário é o penúltimo valor com vírgula (conforme imagem)
                try:
                    preco_unit = float(partes[-2].replace(".", "").replace(",", "."))
                    dados.append({"sku": sku, "produto": nome_prod, "preco": preco_unit, "cliente": cliente, "fone": fone})
                except: continue
    return pd.DataFrame(dados)

# --- INTERFACE ---
st.title("📦 AM Representações")

menu = st.sidebar.selectbox("Ir para:", ["📥 Importar Pedido", "📰 Jornal de Ofertas", "🔥 Cruzamento", "📈 Relatórios"])

if menu == "📥 Importar Pedido":
    st.header("Importar Pedido Depecil")
    arq = st.file_uploader("Arraste o PDF aqui", type="pdf")
    if arq:
        df = ler_pdf_depecil_final(arq)
        if not df.empty:
            st.success(f"✅ Cliente: {df['cliente'].iloc[0]}")
            st.dataframe(df[['sku', 'produto', 'preco']]) # Aqui o nome agora deve aparecer
            if st.button("Salvar no Histórico"):
                for _, r in df.iterrows():
                    cursor.execute("INSERT INTO historico (cliente, fone, sku, produto, preco, data) VALUES (?,?,?,?,?,?)",
                                   (r['cliente'], r['fone'], r['sku'], r['produto'], r['preco'], datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
                st.success("Salvo com sucesso!")
        else:
            st.error("O sistema não conseguiu ler os produtos. Verifique o PDF.")

# As outras abas (Jornal, Cruzamento, Relatórios) seguem a mesma lógica simplificada...
