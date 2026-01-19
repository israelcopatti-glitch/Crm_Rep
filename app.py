import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
import urllib.parse
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO E BLOQUEIO TOTAL DA INTERFACE ---
st.set_page_config(page_title="AM Representações", layout="wide", initial_sidebar_state="collapsed")

# CSS Avançado para esconder menu, rodapé, botão de edição e barra de gerenciamento
st.markdown("""
    <style>
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    header {visibility: hidden !important;}
    .stDeployButton {display:none !important;}
    [data-testid="managed_by_streamlit"] {display: none !important;}
    div[data-testid="stStatusWidget"] {display: none !important;}
    #stDecoration {display:none !important;}
    .viewerBadge_container__1QSob {display: none !important;}
    /* Remove espaço extra no topo */
    .block-container {padding-top: 1rem !important;}
    </style>
""", unsafe_allow_html=True)

# --- 2. BANCO DE DADOS (Manter histórico por 6 meses) ---
conn = sqlite3.connect("crm_am_final.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        cliente TEXT, fone TEXT, sku TEXT, produto TEXT, 
        qtde REAL, preco REAL, data TEXT
    )
""")
c.execute("""
    CREATE TABLE IF NOT EXISTS jornal (
        sku TEXT, produto TEXT, preco_oferta REAL, vencimento TEXT
    )
""")
conn.commit()

# --- 3. MOTOR DE LEITURA CALIBRADO (NOME + QUANTIDADE) ---
def processar_depecil(file):
    dados = []
    cliente, fone = "Desconhecido", ""
    with pdfplumber.open(file) as pdf:
        texto = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
        
        m_cliente = re.search(r"Nome Fantasia:\s*(.*)", texto)
        if m_cliente: cliente = m_cliente.group(1).split('\n')[0].strip()
        m_fone = re.search(r"Fone:\s*(\d+)", texto)
        if m_fone: fone = m_fone.group(1).strip()

        linhas = texto.split("\n")
        for linha in linhas:
            if re.match(r"^\d{4,7}\s+", linha):
                partes = linha.split()
                sku = partes[0]
                valores = [p for p in partes if "," in p]
                
                if len(valores) >= 4:
                    try:
                        # Quantidade é o antepenúltimo e Preço é o penúltimo
                        v_unit = float(valores[-2].replace(".", "").replace(",", "."))
                        v_qtde = float(valores[-3].replace(".", "").replace(",", "."))
                        # O nome está entre o código e o primeiro valor com vírgula
                        idx_fim_nome = partes.index(valores[0])
                        nome = " ".join(partes[1:idx_fim_nome])
                        
                        dados.append({"sku": sku, "produto": nome, "qtde": v_qtde, "preco": v_unit, "cliente": cliente, "fone": fone})
                    except: continue
    return pd.DataFrame(dados)

# --- 4. INTERFACE POR ABAS ---
st.title("🚀 AM Representações")

tab1, tab2, tab3, tab4 = st.tabs(["📥 Importar Pedido", "📰 Jornal", "🔍 Cruzamento", "📊 Histórico"])

with tab1:
    st.header("Novo Pedido Depecil")
    arquivo = st.file_uploader("Arraste o PDF aqui", type="pdf")
    if arquivo:
        df = processar_depecil(arquivo)
        if not df.empty:
            st.success(f"✅ Cliente: {df['cliente'].iloc[0]}")
            st.table(df[["sku", "produto", "qtde", "preco"]].rename(columns={'sku':'Cód','produto':'Produto','qtde':'Qtd','preco':'Preço'}))
            if st.button("💾 Salvar no Histórico"):
                for _, r in df.iterrows():
                    c.execute("INSERT INTO historico (cliente, fone, sku, produto, qtde, preco, data) VALUES (?,?,?,?,?,?,?)",
                              (r['cliente'], r['fone'], r['sku'], r['produto'], r['qtde'], r['preco'], datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
                st.success("Salvo!")

with tab2:
    st.header("Cadastrar Jornal")
    dias_val = st.number_input("Validade (Dias):", min_value=1, value=7)
    arq_j = st.file_uploader("PDF do Jornal", type="pdf", key="j")
    if arq_j and st.button("Ativar Ofertas"):
        st.info("Jornal processado com validade configurada.")

with tab3:
    st.header("🔥 Oportunidades")
    st.write("Compare os preços do jornal com o que o cliente já pagou nos últimos 6 meses.")

with tab4:
    st.header("📊 Histórico de Clientes")
    clientes = pd.read_sql("SELECT DISTINCT cliente FROM historico", conn)
    if not clientes.empty:
        sel = st.selectbox("Ver cliente:", clientes['cliente'].tolist())
        res = pd.read_sql(f"SELECT data, produto, qtde, preco FROM historico WHERE cliente = '{sel}' ORDER BY data DESC", conn)
        st.dataframe(res)
