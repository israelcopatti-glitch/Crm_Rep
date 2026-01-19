import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
import urllib.parse
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO E BLOQUEIO DE INTERFACE ---
st.set_page_config(page_title="AM CRM Profissional", layout="wide", initial_sidebar_state="expanded")

# CSS para esconder o menu do Streamlit, o rodapé e o botão de editar
estilo_customizado = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:none;}
    [data-testid="stSidebarNav"] {padding-top: 0rem;}
    </style>
"""
st.markdown(estilo_customizado, unsafe_allow_html=True)

# --- BANCO DE DADOS (SQLite) ---
conn = sqlite3.connect("crm_vendas.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS historico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente TEXT, fone TEXT, sku TEXT, produto TEXT, preco REAL, data TEXT
)""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS jornal_atual (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT, produto_jornal TEXT, preco_oferta REAL, data_vencimento TEXT
)""")
conn.commit()

# --- FUNÇÕES INTERNAS ---
def limpar_jornal_vencido():
    hoje = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("DELETE FROM jornal_atual WHERE data_vencimento < ?", (hoje,))
    conn.commit()

def ler_pedido_depecil(arquivo):
    dados = []
    with pdfplumber.open(arquivo) as pdf:
        texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    
    cliente = re.search(r"Nome Fantasia:\s*(.*)", texto)
    cliente = cliente.group(1).split('\n')[0].strip() if cliente else "Cliente"
    fone = re.search(r"Fone:\s*([\d\s\-]+)", texto)
    fone = "".join(re.findall(r'\d+', fone.group(1))) if fone else ""
    if fone and not fone.startswith("55"): fone = "55" + fone

    for linha in texto.split("\n"):
        partes = linha.split()
        if len(partes) >= 6 and partes[0].isdigit():
            sku = partes[0]
            precos = [p for p in partes if "," in p]
            if len(precos) >= 2:
                try:
                    p_unit = float(precos[-2].replace(".", "").replace(",", "."))
                    nome_prod = " ".join(partes[1:partes.index(precos[0])])
                    dados.append({"sku": sku, "produto": nome_prod, "preco": p_unit, "cliente": cliente, "fone": fone})
                except: continue
    return pd.DataFrame(dados)

def ler_jornal_pdf(arquivo, dias_validade):
    limpar_jornal_vencido()
    vencimento = (datetime.now() + timedelta(days=dias_validade)).strftime("%Y-%m-%d")
    with pdfplumber.open(arquivo) as pdf:
        texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    
    itens = re.findall(r"(\d{1,6})\s+(.*?)\s+.*?([\d,]{2,})$", texto, re.MULTILINE)
    for sku, prod, preco in itens:
        preco_f = float(preco.replace('.', '').replace(',', '.'))
        cursor.execute("INSERT INTO jornal_atual (sku, produto_jornal, preco_oferta, data_vencimento) VALUES (?,?,?,?)",
                       (sku, prod.strip(), preco_f, vencimento))
    conn.commit()

# --- INTERFACE DO USUÁRIO ---
limpar_jornal_vencido()
st.title("🚀 AM Representações - CRM")

menu = st.sidebar.selectbox("Navegação", [
    "📥 Importar Pedido", 
    "📰 Jornal de Ofertas", 
    "🔥 Cruzamento de Dados", 
    "👥 Clientes & Histórico", 
    "📈 Relatórios",
    "⚠️ Clientes Inativos"
])

if menu == "📥 Importar Pedido":
    st.header("Importar Pedido")
    arq = st.file_uploader("Suba o PDF (Padrão Depecil)", type="pdf")
    if arq:
        df = ler_pedido_depecil(arq)
        if not df.empty:
            st.success(f"✅ Identificado: {df['cliente'].iloc[0]}")
            st.table(df[['sku', 'produto', 'preco']])
            if st.button("Salvar no Banco de Dados"):
                for _, r in df.iterrows():
                    cursor.execute("INSERT INTO historico (cliente, fone, sku, produto, preco, data) VALUES (?,?,?,?,?,?)",
                                   (r['cliente'], r['fone'], r['sku'], r['produto'], r['preco'], datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
                st.balloons()
        else: st.error("Erro ao ler PDF.")

elif menu == "📰 Jornal de Ofertas":
    st.header("Cadastrar Novo Jornal")
    validade = st.number_input("Validade (Dias):", min_value=1, max_value=30, value=7)
    arq_j = st.file_uploader("Suba o Jornal PDF", type="pdf")
    if arq_j:
        if st.button("Ativar Ofertas Agora"):
            ler_jornal_pdf(arq_j, validade)
            st.success(f"✅ Ofertas ativadas por {validade} dias!")

elif menu == "🔥 Cruzamento de Dados":
    st.header("Cruzamento Inteligente")
    df_j = pd.read_sql("SELECT * FROM jornal_atual", conn)
    df_h = pd.read_sql("SELECT * FROM historico", conn)
    
    if not df_j.empty and not df_h.empty:
        cruzado = pd.merge(df_j, df_h, on="sku")
        ofertas = cruzado[cruzado['preco_oferta'] < cruzado['preco']].drop_duplicates(subset=['sku', 'cliente'])
        
        if not ofertas.empty:
            cliente_sel = st.selectbox("Cliente:", ofertas['cliente'].unique())
            df_envio = ofertas[ofertas['cliente'] == cliente_sel]
            st.table(df_envio[['produto_jornal', 'preco', 'preco_oferta']])
            
            msg = f"Olá, *{cliente_sel}*! 👋 Itens que você comprou baixaram de preço:\n\n"
            for _, r in df_envio.iterrows():
                msg += f"✅ *{r['produto_jornal']}*\nDe: R${r['preco']:.2f} por *R${r['preco_oferta']:.2f}*\n\n"
            
            link = f"https://wa.me/{df_envio['fone'].iloc[0]}?text={urllib.parse.quote(msg)}"
            st.markdown(f"### [👉 ENVIAR WHATSAPP REAL]({link})")
        else: st.info("Nenhuma oferta menor que o histórico.")

elif menu == "📈 Relatórios":
    st.header("Estatísticas de Vendas")
    df_r = pd.read_sql("SELECT produto, COUNT(*) as vendas FROM historico GROUP BY produto", conn)
    if not df_r.empty:
        st.bar_chart(df_r.set_index("produto"))

elif menu == "⚠️ Clientes Inativos":
    st.header("Clientes Inativos")
    dias = st.slider("Dias parado:", 7, 60, 30)
    inativos = pd.read_sql(f"SELECT cliente, MAX(data) as ultima, fone FROM historico GROUP BY cliente HAVING ultima <= DATE('now', '-{dias} days')", conn)
    st.table(inativos)
