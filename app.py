import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
import urllib.parse
from datetime import datetime, timedelta

# --- 1. BLOQUEIO TOTAL DA INTERFACE (REMOVE 'GERENCIAR APLICATIVO') ---
st.set_page_config(page_title="AM CRM", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    /* Esconde menu, rodapé e barra de gestão do Streamlit */
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    header {visibility: hidden !important;}
    .stDeployButton {display:none !important;}
    [data-testid="managed_by_streamlit"] {display: none !important;}
    div[data-testid="stStatusWidget"] {display: none !important;}
    #stDecoration {display:none !important;}
    /* Remove a barra preta inferior para usuários não logados */
    .viewerBadge_container__1QSob {display: none !important;}
    </style>
""", unsafe_allow_html=True)

# --- 2. BANCO DE DADOS ---
conn = sqlite3.connect("crm_am_final.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, produto TEXT, preco REAL, data TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS jornal (sku TEXT, produto TEXT, preco_oferta REAL, vencimento TEXT)")
conn.commit()

# --- 3. LEITOR DEPECIL AJUSTADO (CAPTURAR NOME CORRETAMENTE) ---
def ler_pdf_depecil_v4(arquivo):
    dados = []
    cliente = "Desconhecido"
    
    with pdfplumber.open(arquivo) as pdf:
        texto_completo = ""
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"
        
        # Busca Cliente
        m_cliente = re.search(r"Nome Fantasia:\s*(.*)", texto_completo)
        if m_cliente:
            cliente = m_cliente.group(1).split("\n")[0].strip()

        linhas = texto_completo.split("\n")
        for linha in linhas:
            partes = linha.split()
            # Se a linha começa com o SKU (Código) numérico
            if len(partes) > 5 and partes[0].isdigit():
                sku = partes[0]
                
                # LÓGICA DO NOME: Pegamos tudo entre o SKU e o primeiro valor com vírgula (impostos)
                indices_com_virgula = [i for i, p in enumerate(partes) if "," in p]
                if indices_com_virgula:
                    fim_nome_idx = indices_com_virgula[0]
                    nome_produto = " ".join(partes[1:fim_nome_idx])
                    
                    # O Preço Unitário é o penúltimo valor da linha (padrão Depecil)
                    try:
                        preco_unit = float(partes[-2].replace(".", "").replace(",", "."))
                        dados.append({
                            "Cód/SKU": sku, 
                            "Nome do Produto": nome_produto, 
                            "Preço Pago": preco_unit,
                            "Cliente": cliente
                        })
                    except: continue
    return pd.DataFrame(dados)

# --- 4. INTERFACE ---
st.title("📦 AM Representações")

menu = st.sidebar.selectbox("Menu", ["📥 Importar Pedido", "🔥 Cruzamento", "📅 Validade Jornal"])

if menu == "📥 Importar Pedido":
    st.header("Importar Pedido Depecil")
    arq = st.file_uploader("Suba o PDF", type="pdf")
    
    if arq:
        df = ler_pdf_depecil_v4(arq)
        if not df.empty:
            st.success(f"✅ Identificado: {df['Cliente'].iloc[0]}")
            # AGORA O NOME APARECERÁ AQUI
            st.dataframe(df[["Cód/SKU", "Nome do Produto", "Preço Pago"]])
            
            if st.button("💾 Salvar no Histórico de 6 Meses"):
                for _, r in df.iterrows():
                    cursor.execute("INSERT INTO historico (cliente, sku, produto, preco, data) VALUES (?,?,?,?,?)",
                                   (r['Cliente'], r['Cód/SKU'], r['Nome do Produto'], r['Preço Pago'], datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
                st.success("Dados salvos permanentemente!")
        else:
            st.error("Erro na leitura. Verifique se o PDF é o original da Depecil.")

# (Outras abas como Cruzamento e Jornal seguem a mesma lógica)
