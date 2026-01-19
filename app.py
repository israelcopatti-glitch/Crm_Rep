import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO (Oculta menus para ganhar espaço) ---
st.set_page_config(page_title="AM CRM", layout="wide")
st.markdown("<style>header, footer, #MainMenu {visibility: hidden !important;}</style>", unsafe_allow_html=True)

# Mudamos o nome do arquivo para forçar um banco novo e limpo (evita tela branca)
DB_NAME = "am_crm_v2026_lotes_final.db"

# --- 2. BANCO DE DADOS (ABRE E FECHA NA HORA) ---
def execute_db(query, params=()):
    try:
        with sqlite3.connect(DB_NAME, timeout=20) as conn:
            conn.execute(query, params)
            conn.commit()
    except Exception as e:
        st.error(f"Erro no banco: {e}")

def query_db(query, params=()):
    try:
        with sqlite3.connect(DB_NAME, timeout=20) as conn:
            return pd.read_sql(query, conn, params=params)
    except:
        return pd.DataFrame()

# Inicialização das tabelas com a coluna 'lote'
execute_db("""CREATE TABLE IF NOT EXISTS historico (
    id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, fone TEXT, sku TEXT, 
    produto TEXT, qtde REAL, preco REAL, data TEXT, lote TEXT)""")

execute_db("""CREATE TABLE IF NOT EXISTS jornal (
    id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, produto TEXT, 
    preco_oferta REAL, validade TEXT, lote TEXT)""")

# --- 3. MOTOR DE EXTRAÇÃO ---
def extrair_pdf(file):
    lista = []
    cli, fon = "Cliente", ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            txt = page.extract_text()
            if not txt: continue
            if cli == "Cliente":
                m_c = re.search(r"Nome Fantasia:\s*(.*)", txt)
                if m_c: cli = m_c.group(1).split('\n')[0].strip()
                m_f = re.search(r"Fone:\s*(\d+)", txt)
                if m_f: fon = m_f.group(1).strip()
            for l in txt.split("\n"):
                if re.match(r"^\d{4,7}\s+", l):
                    pts = l.split()
                    v = [x for x in pts if "," in x]
                    if len(v) >= 4:
                        try:
                            idx = pts.index(v[0])
                            lista.append({
                                "cliente": cli, "fone": fon, "sku": pts[0].strip(), 
                                "produto": " ".join(pts[1:idx]), 
                                "qtde": float(v[-3].replace(".", "").replace(",", ".")), 
                                "preco": float(v[-2].replace(".", "").replace(",", "."))
                            })
                        except: continue
    return pd.DataFrame(lista)

# --- 4. INTERFACE ---
st.title("AM Representações")
t1, t2, t3, t4, t5 = st.tabs(["📥 Pedido", "📰 Jornal", "🔥 Cruzar", "📊 Histórico", "📋 Ofertas"])

with t1:
    f = st.file_uploader("Subir Pedido (PDF)", type="pdf", key="up_p")
    if f:
        df = extrair_pdf(f)
        if not df.empty:
            st.success(f"Lido: {df['cliente'].iloc[0]}")
            if st.button("💾 SALVAR ESTE PEDIDO"):
                hoje = datetime.now().strftime("%Y-%m-%d")
                for _, r in df.iterrows():
                    execute_db("INSERT INTO historico (cliente, fone, sku, produto, qtde, preco, data, lote) VALUES (?,?,?,?,?,?,?,?)", 
                              (r['cliente'], r['fone'], r['sku'], r['produto'], r['qtde'], r['preco'], hoje, f.name))
                st.rerun()

with t2:
    st.subheader("Prazo do Jornal")
    if "d" not in st.session_state: st.session_state.d = 7
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("➖"): st.session_state.d = max(1, st.session_state.d - 1)
    with c2:
        st.markdown(f"<h2 style='text-align: center;'>{st.session_state.d} Dias</h2>", unsafe_allow_html=True)
    with c3:
        if st.button("➕"): st.session_state.d += 1

    dt_venc = (datetime.now() + timedelta(days=st.session_state.d)).strftime("%Y-%m-%d")
    fj = st.file_uploader("Subir Jornal (PDF)", type="pdf", key="up_j")
    if fj and st.button("🚀 ATIVAR ESTE JORNAL"):
        dfj = extrair_pdf(fj)
        if not dfj.empty:
            for _, r in dfj.iterrows():
                execute_db("INSERT INTO jornal (sku, produto, preco_oferta, validade, lote) VALUES (?,?,?,?,?)", 
                          (r['sku'], r['produto'], r['preco'], dt_venc, fj.name))
            st.success(f"Ativado: {fj.name}")
            st.rerun()

with t3:
    # CRUZAMENTO POR SKU (Lógica do Vídeo)
    q = """SELECT h.cliente, h.fone, j.produto, h.preco as preco_antigo, j.preco_oferta, j.validade, j.lote
           FROM jornal j INNER JOIN historico h ON j.sku = h.sku 
           WHERE j.preco_oferta < h.preco GROUP BY h.cliente, j.sku"""
    df_c = query_db(q)
    if not df_c.empty:
        hoje = datetime.now().strftime("%Y-%m-%d")
        df_c['Status'] = df_c['validade'].apply(lambda x: "⚠️ VENCIDO" if x < hoje else "✅ OK")
        st.dataframe(df_c, use_container_width=True)
    else:
        st.info("Nenhuma oferta encontrada para os clientes do histórico.")

with t4:
    # Histórico de 6 meses (sem perder dados)
    clis = query_db("SELECT DISTINCT cliente FROM historico")
    if not clis.empty:
        sel = st.selectbox("Filtrar Cliente:", ["Todos"] + clis['cliente'].tolist())
        query = "SELECT id, cliente, produto, preco, data, lote FROM historico"
        if sel != "Todos": query += f" WHERE cliente='{sel}'"
        st.dataframe(query_db(query + " ORDER BY id DESC"), use_container_width=True)
        
        idx = st.number_input("ID para apagar item:", min_value=0)
        if st.button("Remover Item"):
            execute_db("DELETE FROM historico WHERE id=?", (idx,))
            st.rerun()

with t5:
    st.subheader("Gerenciar Jornais")
    # LISTA APENAS O NOME DO ARQUIVO (LOTE) - MUITO MAIS LEVE
    lotes = query_db("SELECT lote, validade, COUNT(*) as itens FROM jornal GROUP BY lote")
    if not lotes.empty:
        hoje_t5 = datetime.now().strftime("%Y-%m-%d")
        lotes['Aviso'] = lotes['validade'].apply(lambda x: "🚨 EXPIRADO" if x < hoje_t5 else "✓ VÁLIDO")
        st.table(lotes)
        
        excluir = st.selectbox("Selecionar arquivo para remover:", lotes['lote'].tolist())
        if st.button(f"🗑️ APAGAR TUDO DO ARQUIVO: {excluir}"):
            execute_db("DELETE FROM jornal WHERE lote=?", (excluir,))
            st.rerun()
    else:
        st.write("Nenhum jornal ativo.")
