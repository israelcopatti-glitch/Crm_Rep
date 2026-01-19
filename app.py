import streamlit as st
from motor_extracao import (
    extrair_jornal,
    extrair_pedido,
    salvar_ofertas,
    salvar_pedido
)

st.set_page_config(layout="wide")
st.title("CRM Representante Comercial")

menu = st.sidebar.selectbox("Menu", [
    "Importar Pedido PDF",
    "Jornal de Ofertas",
    "Cruzamento",
    "Histórico",
    "Relatórios",
    "Alertas"
])

# ========== IMPORTAR PEDIDO PDF ==========

if menu == "Importar Pedido PDF":
    st.header("Importar Pedido em PDF")

    arquivo = st.file_uploader("Selecione o pedido em PDF", type=["pdf"])

    if st.button("Processar Pedido") and arquivo:
        with open("temp_pedido.pdf", "wb") as f:
            f.write(arquivo.read())

        cliente, data, itens = extrair_pedido("temp_pedido.pdf")
        salvar_pedido(cliente, data, itens)

        st.success(f"Pedido importado com sucesso ({len(itens)} itens)")

        st.subheader("Cliente")
        st.json(cliente)

        st.subheader("Itens")
        st.table(itens)

# ========== IMPORTAR JORNAL PDF ==========

elif menu == "Jornal de Ofertas":
    st.header("Importar Jornal de Ofertas (PDF)")

    arquivo = st.file_uploader("Selecione o jornal em PDF", type=["pdf"])
    validade = st.text_input("Validade (ex: 23/01/2026)")
    edicao = st.text_input("Edição do Jornal")

    if st.button("Processar Jornal") and arquivo:
        with open("temp_jornal.pdf", "wb") as f:
            f.write(arquivo.read())

        ofertas = extrair_jornal("temp_jornal.pdf", validade, edicao)
        salvar_ofertas(ofertas)

        st.success(f"{len(ofertas)} ofertas importadas com sucesso!")

# ========== PLACEHOLDERS ==========

elif menu == "Cruzamento":
    st.info("Módulo em desenvolvimento")

elif menu == "Histórico":
    st.info("Módulo em desenvolvimento")

elif menu == "Relatórios":
    st.info("Módulo em desenvolvimento")

elif menu == "Alertas":
    st.info("Módulo em desenvolvimento")
