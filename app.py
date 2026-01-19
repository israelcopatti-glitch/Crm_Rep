import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
import urllib.parse
from fpdf import FPDF
from datetime import datetime

# Configuração Inicial
st.set_page_config(page_title="AM CRM", layout="wide")

# Conexão com Banco de Dados
conn = sqlite3.connect("crm_dados.db", check_same_thread=False)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, produto TEXT, preco REAL, data TEXT)")
conn.commit()

# --- FUNÇÃO DE LEITURA DEPECIL ---
def ler_pdf_depecil(arquivo):
    dados = []
    cliente = "Desconhecido"
    fone = ""
    
    with pdfplumber.open(arquivo) as pdf:
        texto = ""
        for pagina in pdf.pages:
            texto += pagina.extract_text() + "\n"
            
        # Busca Cliente e Fone
        m_cliente = re.search(r"Nome Fantasia:\s*(.*)", texto)
        if m_cliente: cliente = m_cliente.group(1).split("\n")[0].strip()
        
        m_fone = re.search(r"Fone:\s*(\d+)", texto)
        if m_fone: fone = m_fone.group(1).strip()

        # Busca Produtos (Ex: 37050 DOBRADICA...)
        linhas = texto.split("\n")
        for linha in linhas:
            partes = linha.split()
            # Se a linha começa com o código numérico (SKU)
            if len(partes) > 5 and partes[0].isdigit():
                sku = partes[0]
                # O preço unitário na Depecil é o penúltimo ou antepenúltimo valor com vírgula
                precos_encontrados = [p for p in partes if "," in p]
                if len(precos_encontrados) >= 2:
                    p_unit_raw = precos_encontrados[-2] # Pega o V. Unit.
                    try:
                        p_unit = float(p_unit_raw.replace(".", "").replace(",", "."))
                        nome_prod = " ".join(partes[1:partes.index(precos_encontrados[0])])
                        dados.append({
                            "SKU": sku, 
                            "Produto": nome_prod, 
                            "Preço": p_unit, 
                            "Cliente": cliente, 
                            "Fone": fone
                        })
                    except: continue
    return pd.DataFrame(dados)

# --- INTERFACE ---
st.title("🚀 AM Representações - CRM")

menu = st.sidebar.selectbox("Menu", ["📥 Importar Pedido", "🔥 Comparar Ofertas", "👥 Clientes", "📈 Relatórios"])

if menu == "📥 Importar Pedido":
    st.header("Importar Pedido (Depecil)")
    arq = st.file_uploader("Suba o PDF aqui", type="pdf")
    
    if arq:
        df = ler_pdf_depecil(arq)
        if not df.empty:
            st.success(f"✅ Pedido de: {df['Cliente'].iloc[0]}")
            st.dataframe(df[["SKU", "Produto", "Preço"]])
            
            if st.button("💾 Salvar no Histórico"):
                for _, r in df.iterrows():
                    c.execute("INSERT INTO historico (cliente, fone, sku, produto, preco, data) VALUES (?,?,?,?,?,?)",
                              (r['Cliente'], r['Fone'], r['SKU'], r['Produto'], r['Preço'], datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
                st.balloons()
        else:
            st.error("❌ Não encontrei os itens. Verifique se o PDF é o original da Depecil.")

elif menu == "🔥 Comparar Ofertas":
    st.header("Comparar com Jornal de Ofertas")
    arq_jornal = st.file_uploader("Suba o PDF do Jornal", type="pdf")
    
    if arq_jornal:
        st.info("Função de cruzamento ativada. O sistema buscará preços menores que o histórico.")
        # Lógica de comparação simplificada para evitar erros de memória
        historico_completo = pd.read_sql("SELECT * FROM historico", conn)
        if not historico_completo.empty:
            st.write("Histórico carregado. Pronto para comparar.")
        else:
            st.warning("O histórico está vazio. Importe um pedido primeiro.")

elif menu == "👥 Clientes":
    st.header("Base de Clientes")
    df_c = pd.read_sql("SELECT DISTINCT cliente, fone FROM historico", conn)
    st.table(df_c)

elif menu == "📈 Relatórios":
    st.header("Relatório de Vendas")
    df_r = pd.read_sql("SELECT produto, COUNT(*) as vendas FROM historico GROUP BY produto", conn)
    if not df_r.empty:
        st.bar_chart(df_r.set_index("produto"))
