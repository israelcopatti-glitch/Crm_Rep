import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO E BLOQUEIO DE INTERFACE ---
st.set_page_config(page_title="AM CRM", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    header, footer, #MainMenu {visibility: hidden !important;}
    .stDeployButton {display:none !important;}
    [data-testid="managed_by_streamlit"] {display: none !important;}
    [data-testid="stHeader"] {display: none !important;}
    #stDecoration {display:none !important;}
    button[title="View source"] {display:none !important;}
    .block-container {padding-top: 1rem !important;}
    </style>
""", unsafe_allow_html=True)

# --- 2. BANCO DE DADOS (ANTI-DUPLICIDADE E PERSISTÊNCIA) ---
def conectar_db():
    conn = sqlite3.connect("crm_am_final_v10.db", check_same_thread=False)
    c = conn.cursor()
    # Histórico de 6 meses com trava de duplicidade
    c.execute("""CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, 
        sku TEXT, produto TEXT, qtde REAL, preco REAL, data TEXT,
        UNIQUE(cliente, sku, data, preco))""")
    # Jornal com validade individual
    c.execute("""CREATE TABLE IF NOT EXISTS jornal (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, produto TEXT, 
        preco_oferta REAL, validade TEXT,
        UNIQUE(sku, preco_oferta, validade))""")
    conn.commit()
    return conn

conn = conectar_db()

# --- 3. MOTOR DE LEITURA (NOME COMPLETO, QTD E FONE REAL) ---
def extrair_dados_pdf(file):
    dados = []
    cliente, fone = "Desconhecido", ""
    try:
        with pdfplumber.open(file) as pdf:
            texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
            
            # Captura Cliente e Telefone Real
            m_cli = re.search(r"Nome Fantasia:\s*(.*)", texto)
            cliente = m_cli.group(1).split('\n')[0].strip() if m_cli else "Cliente"
            m_fon = re.search(r"Fone:\s*(\d+)", texto)
            fone = m_fon.group(1).strip() if m_fon else ""

            for linha in texto.split("\n"):
                if re.match(r"^\d{4,7}\s+", linha):
                    partes = linha.split()
                    sku = partes[0]
                    vals_com_virgula = [p for p in partes if "," in p]
                    
                    if len(vals_com_virgula) >= 4:
                        try:
                            # Captura o nome completo do produto
                            idx_fim_nome = partes.index(vals_com_virgula[0])
                            nome_completo = " ".join(partes[1:idx_fim_nome])
                            
                            # Captura Quantidade (60,00) e Preço (31,6236)
                            qtde = float(vals_com_virgula[-3].replace(".", "").replace(",", "."))
                            preco = float(vals_com_virgula[-2].replace(".", "").replace(",", "."))
                            
                            dados.append({
                                "cliente": cliente, "fone": fone, "sku": sku, 
                                "produto": nome_completo, "qtde": qtde, "preco": preco
                            })
                        except: continue
    except Exception as e:
        st.error(f"Erro ao ler PDF: {e}")
    return pd.DataFrame(dados)

# --- 4. ABAS E FUNCIONALIDADES ---
st.title("🚀 AM Representações")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📥 Novo Pedido", "📰 Novo Jornal", "🔥 Cruzamento", "📊 Histórico", "📋 Gestão Jornal"
])

with tab1:
    st.subheader("Importar Pedido Depecil")
    if "res_p" not in st.session_state: st.session_state.res_p = 0
    arq = st.file_uploader("Suba o PDF", type="pdf", key=f"p_{st.session_state.res_p}")
    
    if arq:
        df = extrair_dados_pdf(arq)
        if not df.empty:
            st.success(f"✅ Cliente: {df['cliente'].iloc[0]}")
            st.table(df[["sku", "produto", "qtde", "preco"]])
            
            if st.button("💾 Salvar Pedido"):
                c = conn.cursor()
                sucesso, avisos = 0, 0
                for _, r in df.iterrows():
                    try:
                        c.execute("""INSERT INTO historico (cliente, fone, sku, produto, qtde, preco, data) 
                                     VALUES (?,?,?,?,?,?,?)""",
                                  (r['cliente'], r['fone'], r['sku'], r['produto'], r['qtde'], r['preco'], 
                                   datetime.now().strftime("%Y-%m-%d")))
                        sucesso += 1
                    except sqlite3.IntegrityError: avisos += 1
                conn.commit()
                if sucesso > 0: st.success(f"Salvo com sucesso!"); st.balloons()
                if avisos > 0: st.warning(f"{avisos} itens já existiam no histórico hoje.")
                st.session_state.res_p += 1
                st.rerun()

with tab2:
    st.subheader("Importar Jornal de Ofertas")
    if "res_j" not in st.session_state: st.session_state.res_j = 0
    data_venc = st.date_input("Vencimento individual deste Jornal:", datetime.now() + timedelta(days=7))
    arq_j = st.file_uploader("Suba o PDF do Jornal", type="pdf", key=f"j_{st.session_state.res_j}")
    
    if arq_j and st.button("Ativar Ofertas"):
        df_j = extrair_dados_pdf(arq_j)
        if not df_j.empty:
            c = conn.cursor()
            for _, r in df_j.iterrows():
                try:
                    c.execute("""INSERT INTO jornal (sku, produto, preco_oferta, validade) 
                                 VALUES (?,?,?,?)""",
                              (r['sku'], r['produto'], r['preco'], data_venc.strftime("%Y-%m-%d")))
                except sqlite3.IntegrityError: pass
            conn.commit()
            st.success("✅ Jornal cadastrado!")
            st.session_state.res_j += 1
            st.rerun()

with tab3:
    st.subheader("🔥 Oportunidades WhatsApp")
    # Limpa vencidos antes de mostrar
    conn.execute("DELETE FROM jornal WHERE validade < ?", (datetime.now().strftime("%Y-%m-%d"),))
    df_h = pd.read_sql("SELECT * FROM historico", conn)
    df_o = pd.read_sql("SELECT * FROM jornal", conn)
    
    if not df_o.empty and not df_h.empty:
        cruzado = pd.merge(df_o, df_h, on="sku", suffixes=('_jor', '_hist'))
        oportunidades = cruzado[cruzado['preco_oferta'] < cruzado['preco']].drop_duplicates(subset=['cliente', 'sku'])
        if not oportunidades.empty:
            st.dataframe(oportunidades[['cliente', 'produto_jor', 'preco', 'preco_oferta', 'validade']])
        else: st.info("Nenhuma oferta abaixo do histórico encontrada.")

with tab4:
    st.subheader("📊 Histórico e Exclusão")
    clientes = pd.read_sql("SELECT DISTINCT cliente FROM historico", conn)
    if not clientes.empty:
        sel = st.selectbox("Pesquisar Cliente:", ["Todos"] + clientes['cliente'].tolist())
        query = "SELECT * FROM historico" + (f" WHERE cliente = '{sel}'" if sel != "Todos" else "") + " ORDER BY id DESC"
        df_ver = pd.read_sql(query, conn)
        
        id_del = st.number_input("ID para excluir pedido:", min_value=0, step=1)
        if st.button("🗑️ Remover do Histórico"):
            conn.execute(f"DELETE FROM historico WHERE id = {id_del}")
            conn.commit(); st.rerun()
        st.dataframe(df_ver)

with tab5:
    st.subheader("📋 Gestão de Ofertas Ativas")
    df_j_ver = pd.read_sql("SELECT * FROM jornal ORDER BY validade ASC", conn)
    if not df_j_ver.empty:
        id_j_del = st.number_input("ID para excluir oferta:", min_value=0, step=1)
        if st.button("🗑️ Remover Oferta"):
            conn.execute(f"DELETE FROM jornal WHERE id = {id_j_del}")
            conn.commit(); st.rerun()
        st.dataframe(df_j_ver)
