import streamlit as st
import pandas as pd
from extratores import extrair_pedido_pdf, extrair_jornal_pdf, extrair_jornal_excel

st.set_page_config(layout="wide")
st.title("CRM Representante Comercial")

menu = st.sidebar.radio(
    "Menu",
    ["Importar Pedidos DEPECIL", "Importar Jornal", "Outros Modulos"]
)

# ================= PEDIDOS =================

if menu == "Importar Pedidos DEPECIL":
    st.header("Importar Pedidos DEPECIL (PDF)")

    arquivo = st.file_uploader("Selecione o pedido em PDF", type=["pdf"])

    if st.button("Processar Pedido"):
        if not arquivo:
            st.warning("Selecione um PDF.")
        else:
            pedidos = extrair_pedido_pdf(arquivo)

            st.success(f"{len(pedidos)} itens importados")

            tabela = []
            for cli, fone, sku, produto, valor in pedidos:
                tabela.append({
                    "Cliente": cli,
                    "Telefone": fone,
                    "Codigo": sku,
                    "Produto": produto,
                    "Valor": valor
                })

            st.table(tabela)

# ================= JORNAL =================

elif menu == "Importar Jornal":
    st.header("Importar Jornal de Ofertas")

    arquivo = st.file_uploader("Selecione PDF ou Excel", type=["pdf", "xlsx", "csv"])

    if st.button("Processar Jornal"):
        if not arquivo:
            st.warning("Selecione um arquivo.")
        else:
            if arquivo.name.lower().endswith(".pdf"):
                ofertas = extrair_jornal_pdf(arquivo)
            else:
                df = pd.read_excel(arquivo) if arquivo.name.endswith("xlsx") else pd.read_csv(arquivo)
                ofertas = extrair_jornal_excel(df)

            st.success(f"{len(ofertas)} ofertas importadas")

            tabela = []
            for sku, produto, preco in ofertas:
                tabela.append({
                    "Codigo": sku,
                    "Produto": produto,
                    "Preco": preco
                })

            st.table(tabela)

else:
    st.info("Demais modulos permanecem inalterados.")
