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

# ================= PEDIDO =================

if menu == "Importar Pedido PDF":
    st.header("Importar Pedido PDF")

    arquivo = st.file_uploader("Selecione o pedido em PDF", type=["pdf"])

    if st.button("Processar Pedido") and arquivo:
        with open("temp_pedido.pdf", "wb") as f:
            f.write(arquivo.read())

        cliente, data, itens = extrair_pedido("temp_pedido.pdf")
        salvar_pedido(cliente, data, ite_
