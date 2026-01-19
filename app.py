import streamlit as st
from motor_extracao import (
    extrair_jornal,
    extrair_pedido,
    salvar_ofertas,
    salvar_pedido
)

st.set_page_config(layout="wide")
st.title("CRM Representante Comercial")

# ===== CONTROLE DE NAVEGACAO =====

if "tela" not in st.session_state:
    st.session_state.tela = "home"

def ir(tela):
    st.session_state.tela = tela

# ===== MENU PRINCIPAL =====

st.markdown("### Menu Principal")

c1, c2, c3 = st.columns(3)
c4, c5, c6 = st.columns(3)

c1.button("Pedido PDF", use_container_width=True, on_click=ir, args=("pedido",))
c2.button("Jornal PDF", use_container_width=True, on_click=ir, args=("jornal",))
c3.button("Cruzamento", use_container_width=True, on_click=ir, args=("cruzamento",))
c4.button("Historico", use_container_width=True, on_click=ir, args=("historico",))
c5.button("Relatorios", use_container_width=True, on_click=ir, args=("relatorios",))
c6.button("Alertas", use_container_width=True, on_click=ir, args=("alertas",))

st.divider()

# ===== TELAS =====

if st.session_state.tela == "home":
    st.info("Selecione uma funcao acima.")

elif st.session_state.tela == "pedido":
    st.header("Importar Pedido PDF")

    arquivo = st.file_uploader("Selecione o pedido em PDF", type=["pdf"])

    if st.button("Processar Pedido"):

        if arquivo is None:
            st.warning("Selecione um PDF.")
        else:
            try:
                with open("temp_pedido.pdf", "wb") as f:
                    f.write(arquivo.read())

                cliente, data, itens = extrair_pedido("temp_pedido.pdf")
                salvar_pedido(cliente, data, itens)

                st.success("Pedido importado com sucesso.")
                st.write("Itens importados:", len(itens))

                st.subheader("Cliente")
                st.json(cliente)

                st.subheader("Itens")
                st.table(itens)

            except Exception as e:
                st.error("Erro ao importar pedido: " + str(e))

elif st.session_state.tela == "jornal":
    st.header("Importar Jornal PDF")

    arquivo = st.file_uploader("Selecione o jornal em PDF", type=["pdf"])
    validade = st.text_input("Validade do jornal")
    edicao = st.text_input("Edicao do jornal")

    if st.button("Processar Jornal"):

        if arquivo is None:
            st.warning("Selecione um PDF.")
        elif validade.strip() == "":
            st.warning("Informe a validade.")
        else:
            try:
                with open("temp_jornal.pdf", "wb") as f:
                    f.write(arquivo.read())

                ofertas = extrair_jornal("temp_jornal.pdf", validade, edicao)
                salvar_ofertas(ofertas)

                st.success("Jornal importado com sucesso.")
                st.write("Ofertas importadas:", len(ofertas))

            except Exception as e:
                st.error("Erro ao importar jornal: " + str(e))

elif st.session_state.tela == "cruzamento":
    st.info("Modulo de cruzamento em desenvolvimento.")

elif st.session_state.tela == "historico":
    st.info("Modulo de historico em desenvolvimento.")

elif st.session_state.tela == "relatorios":
    st.info("Modulo de relatorios em desenvolvimento.")

elif st.session_state.tela == "alertas":
    st.info("Modulo de alertas em desenvolvimento.")
