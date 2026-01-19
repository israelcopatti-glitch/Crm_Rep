import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="AM CRM", layout="wide")

# CSS Simples para não quebrar a tela
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    </style>
""", unsafe_allow_html=True)

# --- BANCO DE DADOS ---
conn = sqlite3.connect("crm_am_v7.db", check_same_thread=False)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, sku TEXT, produto TEXT, qtde REAL, preco REAL, data TEXT)")
conn.commit()

def processar_depecil(file):
    dados = []
    cliente = "Desconhecido"
    with pdfplumber.open(file) as pdf:
        texto = ""
        for page in pdf.pages:
            texto += page.extract_text() + "\n"
        
        # [span_1](start_span)Captura Cliente[span_1](end_span)
        m_cliente = re.search(r"Nome Fantasia:\s*(.*)", texto)
        if m_cliente:
            cliente = m_cliente.group(1).split('\n')[0].strip()

        linhas = texto.split("\n")
        for linha in linhas:
            # [span_2](start_span)Detecta linha que começa com número (SKU)[span_2](end_span)
            if re.match(r"^\d{4,7}\s+", linha):
                partes = linha.split()
                sku = partes[0]
                
                # [span_3](start_span)Identifica todos os valores com vírgula (impostos, qtde, preço)[span_3](end_span)
                valores = [p for p in partes if "," in p]
                
                if len(valores) >= 4:
                    try:
                        # [span_4](start_span)No seu PDF[span_4](end_span):
                        # O último é o Total
                        # O penúltimo é o Valor Unitário (31,6236)
                        # O antepenúltimo é a Quantidade (60,00)
                        v_unit = float(valores[-2].replace(".", "").replace(",", "."))
                        v_qtde = float(valores[-3].replace(".", "").replace(",", "."))
                        
                        # O nome está entre o SKU e o primeiro valor com vírgula
                        idx_fim_nome = partes.index(valores[0])
                        nome = " ".join(partes[1:idx_fim_nome])
                        
                        dados.append({
                            "SKU": sku,
                            "Produto": nome,
                            "Qtde": v_qtde,
                            "Preço": v_unit,
                            "Cliente": cliente
                        })
                    except:
                        continue
    return pd.DataFrame(dados)

# --- INTERFACE ---
st.title("🚀 AM Representações")

uploaded_file = st.file_uploader("Suba o pedido Depecil (PDF)", type="pdf")

if uploaded_file:
    df = processar_depecil(uploaded_file)
    
    if not df.empty:
        st.success(f"✅ Pedido de: {df['Cliente'].iloc[0]}")
        # [span_5](start_span)Exibe a tabela com as colunas solicitadas[span_5](end_span)
        st.table(df[["SKU", "Produto", "Qtde", "Preço"]])
        
        if st.button("💾 Salvar no Histórico"):
            for _, r in df.iterrows():
                c.execute("INSERT INTO historico (cliente, sku, produto, qtde, preco, data) VALUES (?,?,?,?,?,?)",
                          (r['Cliente'], r['SKU'], r['Produto'], r['Qtde'], r['Preço'], datetime.now().strftime("%Y-%m-%d")))
            conn.commit()
            st.success("Dados salvos!")
    else:
        st.error("Não foi possível extrair os dados. Verifique o formato do PDF.")
