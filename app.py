import streamlit as st
from datetime import date
from db import conn, cur
from extratores import extrair_pedido_pdf, extrair_jornal_pdf

st.set_page_config(page_title="CRM Representante", layout="centered")

st.title("📊 CRM Representante Comercial")

menu = st.radio("Menu", [
    "Importar Pedido DEPECIL",
    "Jornal de Ofertas PR"
])

# ================= PEDIDO =================
if menu == "Importar Pedido DEPECIL":
    st.header("Importar Pedido PDF")

    pdf = st.file_uploader("Selecione o PDF do pedido", type=["pdf"])

    if st.button("Processar Pedido") and pdf:
        cliente, itens = extrair_pedido_pdf(pdf)

        cur.execute(
            "INSERT INTO CLIENTES (codigo, nome) VALUES (?,?)",
            (cliente["codigo"], cliente["nome"])
        )
        cliente_id = cur.lastrowid

        for i in itens:
            cur.execute("""
                INSERT INTO PEDIDOS
                (cliente_id, data, codigo_prod, nome_prod, qtde, preco_unit, valor_total)
                VALUES (?,?,?,?,?,?,?)
            """, (
                cliente_id,
                str(date.today()),
                i["codigo"],
                i["nome"],
                i["qtde"],
                i["preco"],
                i["total"]
            ))

        conn.commit()
        st.success("Pedido importado com sucesso!")

# ================= JORNAL =================
elif menu == "Jornal de Ofertas PR":
    st.header("Importar Jornal PR")

    pdf = st.file_uploader("Selecione o PDF do Jornal PR", type=["pdf"])
    validade = st.text_input("Validade")
    edicao = st.text_input("Edição")

    if st.button("Processar Jornal") and pdf:
        ofertas = extrair_jornal_pdf(pdf)

        for o in ofertas:
            cur.execute("""
                INSERT INTO OFERTAS
                (codigo_prod, nome_prod, preco_pr, validade, edicao)
                VALUES (?,?,?,?,?)
            """, (o[0], o[1], o[2], validade, edicao))

        conn.commit()
        st.success(f"{len(ofertas)} ofertas importadas!")
