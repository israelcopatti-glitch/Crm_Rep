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
    .viewerBadge_container__1QSob {display:none !important;}
    button[title="View source"] {display:none !important;}
    div[data-testid="stStatusWidget"] {display: none !important;}
    .block-container {padding-top: 1rem !important;}
    </style>
""", unsafe_allow_html=True)

# --- 2. BANCO DE DADOS (COM TRAVAS DE DUPLICIDADE) ---
def conectar_db():
    conn = sqlite3.connect("crm_am_v2026_final_v5.db", check_same_thread=False)
    c = conn.cursor()
    # Unique para evitar duplicar item de cliente no mesmo dia
    c.execute("""CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, 
        sku TEXT, produto TEXT, qtde REAL, preco REAL, data TEXT,
        UNIQUE(cliente, sku, data, preco))""")
    # Unique para evitar duplicar oferta no mesmo período
    c.execute("""CREATE TABLE IF NOT EXISTS jornal (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, produto TEXT, 
        preco_oferta REAL, validade TEXT,
        UNIQUE(sku, preco_oferta, validade))""")
    conn.commit()
    return conn

conn = conectar_db()

# --- 3. MOTOR DE LEITURA (NOME, QTD E FONE DO PDF) ---
def extrair_dados(file):
    dados = []
    cliente, fone = "Desconhecido", ""
    with pdfplumber.open(file) as pdf:
        texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        m_cli = re.search(r"Nome Fantasia:\s*(.*)", texto); cliente = m_cli.group(1).split('\n')[0].strip() if m_cli else "Cliente"
        m_fon = re.search(r"Fone:\s*(\d+)", texto); fone = m_fon.group(1).strip() if m_fon else ""
        for linha in texto.split("\n"):
            if re.match(r"^\d{4,7}\s+", linha):
                partes = linha.split()
                sku = partes[0]
                vals = [p for p in partes if "," in p]
                if len(vals) >= 4:
                    try:
                        idx_fim_nome = partes.index(vals[0])
                        nome = " ".join(partes[1:idx_fim_nome])
                        qtd = float(vals[-3].replace(".", "").replace(",", "."))
                        prc = float(vals[-2].replace(".", "").replace(",", "."))
                        dados.append({"cliente": cliente, "fone": fone, "sku": sku, "produto": nome, "qtde": qtd, "preco": prc})
                    except: continue
    return pd.DataFrame(dados)

# --- 4. INTERFACE ---
st.title("🚀 AM Representações")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📥 Novo Pedido", "📰 Novo Jornal", "🔥 Cruzamento", "📊 Histórico Pedidos", "📋 Ver Ofertas"])

# --- TAB 1: IMPORTAR PEDIDO ---
with tab1:
    st.subheader("Importar Pedido Depecil")
    # Usamos o session_state para limpar o campo após salvar
    if "reset_pedido" not in st.session_state: st.session_state.reset_pedido = 0
    
    arq = st.file_uploader("Suba o PDF", type="pdf", key=f"ped_{st.session_state.reset_pedido}")
    if arq:
        df = extrair_dados(arq)
        if not df.empty:
            st.success(f"✅ Pedido: {df['cliente'].iloc[0]}")
            st.table(df[["sku", "produto", "qtde", "preco"]])
            if st.button("💾 Salvar e Finalizar"):
                c = conn.cursor()
                sucesso, erros = 0, 0
                for _, r in df.iterrows():
                    try:
                        c.execute("INSERT INTO historico (cliente, fone, sku, produto, qtde, preco, data) VALUES (?,?,?,?,?,?,?)",
                                  (r['cliente'], r['fone'], r['sku'], r['produto'], r['qtde'], r['preco'], datetime.now().strftime("%Y-%m-%d")))
                        sucesso += 1
                    except sqlite3.IntegrityError: erros += 1
                conn.commit()
                if sucesso > 0: st.success(f"Salvo: {sucesso} itens."); st.balloons()
                if erros > 0: st.warning(f"Ignorado: {erros} itens já existiam no histórico para hoje.")
                st.session_state.reset_pedido += 1 # Limpa a tela
                st.rerun()

# --- TAB 2: IMPORTAR JORNAL ---
with tab2:
    st.subheader("Importar Jornal de Ofertas")
    if "reset_jornal" not in st.session_state: st.session_state.reset_jornal = 0
    data_val = st.date_input("Válido até:", datetime.now() + timedelta(days=7))
    arq_j = st.file_uploader("PDF do Jornal", type="pdf", key=f"jor_{st.session_state.reset_jornal}")
    if arq_j and st.button("Ativar Jornal"):
        df_j = extrair_dados(arq_j)
        if not df_j.empty:
            c = conn.cursor()
            for _, r in df_j.iterrows():
                try:
                    c.execute("INSERT INTO jornal (sku, produto, preco_oferta, validade) VALUES (?,?,?,?)",
                              (r['sku'], r['produto'], r['preco'], data_val.strftime("%Y-%m-%d")))
                except sqlite3.IntegrityError: pass
            conn.commit()
            st.success("✅ Ofertas ativadas!")
            st.session_state.reset_jornal += 1 # Limpa a tela
            st.rerun()

# --- TAB 3: CRUZAMENTO ---
with tab3:
    st.subheader("🔥 Oportunidades")
    # Limpa vencidos antes de cruzar
    conn.execute("DELETE FROM jornal WHERE validade < ?", (datetime.now().strftime("%Y-%m-%d"),))
    df_h = pd.read_sql("SELECT * FROM historico", conn)
    df_o = pd.read_sql("SELECT * FROM jornal", conn)
    if not df_o.empty and not df_h.empty:
        cruzado = pd.merge(df_o, df_h, on="sku", suffixes=('_jor', '_hist'))
        oportunidades = cruzado[cruzado['preco_oferta'] < cruzado['preco']].drop_duplicates(subset=['cliente', 'sku'])
        st.dataframe(oportunidades[['cliente', 'produto_jor', 'preco', 'preco_oferta', 'validade']])
    else: st.info("Sem dados para cruzamento.")

# --- TAB 4: HISTÓRICO PEDIDOS ---
with tab4:
    st.subheader("📊 Histórico de Clientes (6 Meses)")
    clientes = pd.read_sql("SELECT DISTINCT cliente FROM historico", conn)
    if not clientes.empty:
        sel = st.selectbox("Filtrar Cliente:", ["Todos"] + clientes['cliente'].tolist())
        query = "SELECT * FROM historico" + (f" WHERE cliente = '{sel}'" if sel != "Todos" else "") + " ORDER BY data DESC"
        df_h_ver = pd.read_sql(query, conn)
        
        id_del_p = st.number_input("ID para excluir pedido:", min_value=0, step=1)
        if st.button("🗑️ Excluir Item do Histórico"):
            conn.execute(f"DELETE FROM historico WHERE id = {id_del_p}")
            conn.commit(); st.rerun()
        
        st.dataframe(df_h_ver[['id', 'data', 'cliente', 'produto', 'qtde', 'preco']])

# --- TAB 5: GESTÃO DE OFERTAS ---
with tab5:
    st.subheader("📋 Ofertas Ativas no Jornal")
    df_jor_ver = pd.read_sql("SELECT * FROM jornal ORDER BY validade ASC", conn)
    if not df_jor_ver.empty:
        id_del_j = st.number_input("ID para excluir oferta:", min_value=0, step=1)
        if st.button("🗑️ Excluir Oferta"):
            conn.execute(f"DELETE FROM jornal WHERE id = {id_del_j}")
            conn.commit(); st.rerun()
        st.dataframe(df_jor_ver[['id', 'sku', 'produto', 'preco_oferta', 'validade']])
    else: st.write("Nenhuma oferta cadastrada.")
