import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# --- 1. BLOQUEIO DE INTERFACE (MODO APP PROFISSIONAL) ---
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

# --- 2. BANCO DE DADOS (COM VALIDADE INDIVIDUAL) ---
def conectar_db():
    conn = sqlite3.connect("crm_am_v2026_final.db", check_same_thread=False)
    c = conn.cursor()
    # Histórico de compras (6 meses)
    c.execute("""CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        cliente TEXT, fone TEXT, sku TEXT, produto TEXT, 
        qtde REAL, preco REAL, data TEXT)""")
    # Jornal com validade individual por item
    c.execute("""CREATE TABLE IF NOT EXISTS jornal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT, produto TEXT, preco_oferta REAL, validade TEXT)""")
    conn.commit()
    return conn

conn = conectar_db()

# --- 3. MOTOR DE LEITURA (NOME, QTD E FONE) ---
def extrair_dados(file):
    dados = []
    cliente, fone = "Desconhecido", ""
    with pdfplumber.open(file) as pdf:
        texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        
        m_cli = re.search(r"Nome Fantasia:\s*(.*)", texto)
        if m_cli: cliente = m_cli.group(1).split('\n')[0].strip()
        m_fon = re.search(r"Fone:\s*(\d+)", texto)
        if m_fon: fone = m_fon.group(1).strip()

        for linha in texto.split("\n"):
            if re.match(r"^\d{4,7}\s+", linha):
                partes = linha.split()
                sku = partes[0]
                vals = [p for p in partes if "," in p]
                if len(vals) >= 4:
                    try:
                        # Posição do Nome: entre SKU e o primeiro valor com vírgula
                        idx_fim_nome = partes.index(vals[0])
                        nome = " ".join(partes[1:idx_fim_nome])
                        qtd = float(vals[-3].replace(".", "").replace(",", "."))
                        prc = float(vals[-2].replace(".", "").replace(",", "."))
                        dados.append({"cliente": cliente, "fone": fone, "sku": sku, "produto": nome, "qtde": qtd, "preco": prc})
                    except: continue
    return pd.DataFrame(dados)

# --- 4. INTERFACE ---
st.title("🚀 AM Representações")

tab1, tab2, tab3, tab4 = st.tabs(["📥 Importar Pedido", "📰 Jornal de Ofertas", "🔍 Cruzamento", "📊 Histórico"])

with tab1:
    st.subheader("Novo Pedido Depecil")
    arq = st.file_uploader("Suba o PDF do Pedido", type="pdf")
    if arq:
        df = extrair_dados(arq)
        if not df.empty:
            st.success(f"✅ Pedido: {df['cliente'].iloc[0]}")
            st.table(df[["sku", "produto", "qtde", "preco"]])
            if st.button("💾 Salvar Pedido"):
                c = conn.cursor()
                for _, r in df.iterrows():
                    c.execute("INSERT INTO historico (cliente, fone, sku, produto, qtde, preco, data) VALUES (?,?,?,?,?,?,?)",
                              (r['cliente'], r['fone'], r['sku'], r['produto'], r['qtde'], r['preco'], datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
                st.success("Salvo no histórico!")

with tab2:
    st.subheader("Importar Jornal (Validade Individual)")
    data_val = st.date_input("Este Jornal é válido até:", datetime.now() + timedelta(days=7))
    arq_j = st.file_uploader("Suba o PDF do Jornal", type="pdf", key="jornal")
    
    if arq_j and st.button("Ativar este Jornal"):
        # Processa o jornal e salva com a data escolhida acima
        df_j = extrair_dados(arq_j)
        if not df_j.empty:
            c = conn.cursor()
            for _, r in df_j.iterrows():
                c.execute("INSERT INTO jornal (sku, produto, preco_oferta, validade) VALUES (?,?,?,?)",
                          (r['sku'], r['produto'], r['preco'], data_val.strftime("%Y-%m-%d")))
            conn.commit()
            st.success(f"✅ {len(df_j)} itens adicionados com validade até {data_val.strftime('%d/%m/%Y')}!")

with tab3:
    st.subheader("🔥 Cruzamento de Preços")
    # Limpa ofertas vencidas antes de mostrar
    hoje = datetime.now().strftime("%Y-%m-%d")
    conn.execute("DELETE FROM jornal WHERE validade < ?", (hoje,))
    
    # Busca histórico e ofertas ativas
    df_hist = pd.read_sql("SELECT * FROM historico", conn)
    df_ofertas = pd.read_sql("SELECT * FROM jornal", conn)
    
    if not df_ofertas.empty and not df_hist.empty:
        # Cruza pelo SKU e mostra apenas se o preço do jornal for menor que o pago antes
        cruzado = pd.merge(df_ofertas, df_hist, on="sku", suffixes=('_jor', '_hist'))
        oportunidades = cruzado[cruzado['preco_oferta'] < cruzado['preco']]
        
        if not oportunidades.empty:
            st.write("Itens com preço melhor que o histórico:")
            st.dataframe(oportunidades[['cliente', 'produto_jor', 'preco', 'preco_oferta', 'validade']])
        else:
            st.info("Nenhuma oferta abaixo do preço histórico encontrada no momento.")

with tab4:
    st.subheader("📊 Histórico (6 Meses)")
    seis_meses = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
    df_h = pd.read_sql(f"SELECT * FROM historico WHERE data >= '{seis_meses}' ORDER BY data DESC", conn)
    st.dataframe(df_h, use_container_width=True)
