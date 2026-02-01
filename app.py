import streamlit as st
import pandas as pd
from db import inserir_cliente, inserir_pedido, buscar_cliente_por_codigo
from extratores import extrair_pedido_pdf

# Título do app
st.title("CRM de Representante Comercial")

# Upload do arquivo PDF
uploaded_file = st.file_uploader("Carregue o PDF do pedido", type=["pdf"])

if uploaded_file is not None:
    # Extraindo dados do PDF
    cliente, pedidos = extrair_pedido_pdf(uploaded_file)

    # Verificando se o cliente já está cadastrado
    cliente_existente = buscar_cliente_por_codigo(cliente["codigo"])

    if cliente_existente:
        st.write(f"Cliente encontrado: {cliente_existente[1]}")
        cliente_id = cliente_existente[0]
    else:
        # Inserir novo cliente
        st.write(f"Novo cliente: {cliente['nome']}")
        inserir_cliente(cliente)
        cliente_id = buscar_cliente_por_codigo(cliente["codigo"])[0]

    # Inserir os pedidos
    inserir_pedido(cliente_id, pedidos)
    st.success("Pedidos inseridos com sucesso!")

    # Exibindo dados extraídos
    st.subheader("Cliente")
    st.write(cliente)

    st.subheader("Pedidos")
    pedidos_df = pd.DataFrame(pedidos)
    st.dataframe(pedidos_df)

# Botão para gerar relatórios (Exemplo de exportação para Excel)
if st.button("Gerar Relatório em Excel"):
    pedidos_df.to_excel("relatorio_pedidos.xlsx", index=False)
    st.success("Relatório gerado com sucesso!")
