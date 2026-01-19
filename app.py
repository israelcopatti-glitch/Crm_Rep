import streamlit as st
import pandas as pd
from datetime import date
from extratores import extrair_pedido_pdf, extrair_jornal_pdf, extrair_jornal_excel
from db import get_connection, init_db

st.set_page_config(page_title="Pedidos & Ofertas", layout="wide")

init_db()

tabs = st.tabs(["Registrar Pedido", "Jornal de Ofertas", "Cruzamento"])

# ============================================================
# TAB 1 - REGISTRAR PEDIDO
# ============================================================
with tabs[0]:
    st.header("Registrar Pedido")
    f = st.file_uploader("Enviar Pedido (PDF)", type=["pdf"])

    if f:
        dados = extrair_pedido_pdf(f)
        df = pd.DataFrame(dados, columns=["cliente", "telefone", "sku", "produto", "valor"])
        st.dataframe(df)

        if st.button("Salvar Pedido"):
            conn = get_connection()
            for c, t, s, p, v in dados:
                conn.execute("INSERT INTO pedidos (cliente, telefone, sku, produto, valor, lote) VALUES (?,?,?,?,?,?)",
                             (c, t, s, p, v, f.name))
            conn.commit()
            conn.close()
            st.success("Pedido registrado!")
            st.experimental_rerun()


# ============================================================
# TAB 2 - JORNAL
# ============================================================
with tabs[1]:
    st.header("Jornal de Ofertas")
    f = st.file_uploader("Enviar Jornal", type=["pdf", "xlsx", "csv"])
    validade = st.date_input("Validade", date.today(), format="DD/MM/YYYY")

    if f:
        # Detecta tipo
        if f.name.endswith(".pdf"):
            dados_j = extrair_jornal_pdf(f)
        elif f.name.endswith(".xlsx"):
            df = pd.read_excel(f)
            dados_j = extrair_jornal_excel(df)
        elif f.name.endswith(".csv"):
            df = pd.read_csv(f)
            dados_j = extrair_jornal_excel(df)

        dfj = pd.DataFrame(dados_j, columns=["sku", "produto", "preco_oferta"])
        st.dataframe(dfj)

        if st.button("Ativar Jornal"):
            conn = get_connection()
            for s, p, po in dados_j:
                conn.execute("INSERT INTO jornal (sku, produto, preco_oferta, validade, lote) VALUES (?,?,?,?,?)",
                             (s, p, po, validade, f.name))
            conn.commit()
            conn.close()
            st.success("Jornal ativado!")
            st.experimental_rerun()


# ============================================================
# TAB 3 - CRUZAMENTO
# ============================================================
with tabs[2]:
    st.header("Cruzamento de Pedidos x Ofertas")

    conn = get_connection()

    dfp = pd.read_sql_query("SELECT * FROM pedidos", conn)
    dfj = pd.read_sql_query("SELECT * FROM jornal", conn)

    if dfp.empty or dfj.empty:
        st.warning("Cadastre pedidos e jornal para cruzar")
    else:
        cruz = dfp.merge(dfj, on="sku", how="left")
        cruz["diferenca"] = cruz["valor"] - cruz["preco_oferta"]
        cruz["melhor_oferta"] = cruz["diferenca"] > 0

        st.dataframe(cruz)

        ofertas = cruz[cruz["melhor_oferta"] == True]
        if not ofertas.empty:
            st.success("Clientes com ofertas melhores disponíveis:")
            st.dataframe(ofertas)
        else:
            st.info("Nenhuma oferta melhor encontrada.")

    conn.close()
