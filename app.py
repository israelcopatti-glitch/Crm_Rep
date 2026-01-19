import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime

# --- 1. BLOQUEIO DE INTERFACE (ESCONDE 'GERENCIAR APLICATIVO' E EDIÇÃO) ---
st.set_page_config(page_title="AM Representações", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    /* Esconde botões de menu, deploy, cabeçalho e rodapé */
    header, footer, #MainMenu {visibility: hidden !important;}
    .stDeployButton {display:none !important;}
    [data-testid="managed_by_streamlit"] {display: none !important;}
    [data-testid="stHeader"] {display: none !important;}
    #stDecoration {display:none !important;}
    .viewerBadge_container__1QSob {display:none !important;}
    button[title="View source"] {display:none !important;}
    div[data-testid="stStatusWidget"] {display: none !important;}
    /* Remove preenchimento superior */
    .block-container {padding-top: 1rem !important;}
    </style>
""", unsafe_allow_html=True)

# --- 2. BANCO DE DADOS (HISTÓRICO PERMANENTE) ---
def conectar_db():
    # Novo nome de arquivo para garantir que a tabela seja criada corretamente
    conn = sqlite3.connect("crm_am_v10.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            cliente TEXT, fone TEXT, sku TEXT, produto TEXT, 
            qtde REAL, preco REAL, data TEXT
        )
    """)
    conn.commit()
    return conn

conn = conectar_db()

# --- 3. MOTOR DE LEITURA (CAPTURA NOME E QUANTIDADE REAL) ---
def extrair_dados_depecil(file):
    dados = []
    cliente, fone = "Desconhecido", ""
    with pdfplumber.open(file) as pdf:
        texto = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
        
        # Captura Cliente e Fone Real do PDF
        m_cliente = re.search(r"Nome Fantasia:\s*(.*)", texto)
        if m_cliente: cliente = m_cliente.group(1).split('\n')[0].strip()
        
        m_fone = re.search(r"Fone:\s*(\d+)", texto)
        if m_fone: fone = m_fone.group(1).strip()

        linhas = texto.split("\n")
        for linha in linhas:
            # Detecta linhas que começam com o código SKU (ex: 37050)
            if re.match(r"^\d{4,7}\s+", linha):
                partes = linha.split()
                sku = partes[0]
                
                # Identifica valores com vírgula para separar o Nome da Qtd
                indices_virgula = [i for i, p in enumerate(partes) if "," in p]
                
                if len(indices_virgula) >= 4:
                    try:
                        # O nome do produto está entre o SKU e o primeiro valor de imposto
                        idx_fim_nome = indices_virgula[0]
                        nome_produto = " ".join(partes[1:idx_fim_nome])
                        
                        # Quantidade e Preço (posições fixas no PDF Depecil)
                        v_qtde = float(partes[indices_virgula[-3]].replace(".", "").replace(",", "."))
                        v_unit = float(partes[indices_virgula[-2]].replace(".", "").replace(",", "."))
                        
                        dados.append({
                            "cliente": cliente, "fone": fone, "sku": sku, 
                            "produto": nome_produto, "qtde": v_qtde, "preco": v_unit
                        })
                    except: continue
    return pd.DataFrame(dados)

# --- 4. INTERFACE POR ABAS ---
st.title("🚀 AM Representações")

tab1, tab2, tab3 = st.tabs(["📥 Novo Pedido", "🔍 Histórico", "📰 Jornal"])

with tab1:
    st.subheader("Importar Pedido Depecil")
    arquivo = st.file_uploader("Selecione o arquivo PDF", type="pdf", key="up_pdf")
    
    if arquivo:
        df_pedido = extrair_dados_depecil(arquivo)
        if not df_pedido.empty:
            st.success(f"✅ Identificado: {df_pedido['cliente'].iloc[0]}")
            # Exibe a tabela com o Nome do Produto preenchido
            st.table(df_pedido[["sku", "produto", "qtde", "preco"]].rename(
                columns={'sku':'Cód','produto':'Nome do Produto','qtde':'Qtd','preco':'Preço Unit.'}
            ))
            
            if st.button("💾 Salvar no Histórico Permanentemente"):
                cursor = conn.cursor()
                for _, r in df_pedido.iterrows():
                    cursor.execute("""
                        INSERT INTO historico (cliente, fone, sku, produto, qtde, preco, data) 
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (r['cliente'], r['fone'], r['sku'], r['produto'], r['qtde'], r['preco'], datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
                st.balloons()
                st.success("Dados salvos com sucesso!")

with tab2:
    st.subheader("Consulta de Compras (Últimos 6 meses)")
    df_hist = pd.read_sql("SELECT data, cliente, fone, produto, qtde, preco FROM historico ORDER BY data DESC", conn)
    if not df_hist.empty:
        st.dataframe(df_hist, use_container_width=True)
    else:
        st.info("Nenhum dado no histórico ainda.")

with tab3:
    st.subheader("Jornal de Ofertas")
    st.write("Em desenvolvimento: Compare os preços do jornal com as compras passadas.")
