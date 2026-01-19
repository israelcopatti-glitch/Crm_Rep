import streamlit as st
from motor_extracao import (
    extrair_jornal,
    extrair_pedido,
    salvar_ofertas,
    salvar_pedido
)

st.set_page_config(layout="wide")
st.title("📊 CRM Representante Comercial")

# ================= CONTROLE DE TELA =================

if "tela" not in st.session_state:
    st.session_state.tela = "home"

def ir(tela):
    st.session_state.tela = tela

# ================= MENU PRINCIPAL =================

st.markdown("### Menu Principal")

c1, c2, c3 = st.columns(3)
with c1:
    st.button("📥 Pedido PDF", use_container_width=True, on_click=ir, args=("pedido",))
with c2:
    st.button("📰 Jornal PDF", use_container_width=True, on_click=ir, args=("jornal",))
with c3:
    st.button("📈 Cruzamento", use_container_width=True, on_click=ir, args=("cruzamento",))

c4, c5, c6 = st.columns(3)
with c4:
    st.button("📂 Histórico", use_container_width=True, on_click=ir, args=("historico",))
with c5:
    st.button("📊 Relatórios", use_container_width=True, on_click=ir, args=("relatorios",))
with c6:
    st.button("🚨 Alertas", use_container_width=True, on_click=ir, args=("alertas",))

st.divider()

# ================= TELAS =================

# ---------- HOME ----------
if st.session_state.tela == "home":
    st.info("Selecione uma função acima.")

# ---------- PEDIDO PDF ----------
elif st.session_state.tela == "pedido":
    st.header("📥 Importar Pedido em PDF")

    arquivo = st.file_uploader("Selecione o pedido em PDF", type=["pdf"])

    if st.button("🚀 Processar Pedido", use_container_width=True):

        if not arquivo:
            st.warning("Selecione um PDF antes de processar.")
        else:
            try:
                with open("temp_pedido.pdf", "wb") as f:
                    f.write(arquivo.read())

                cliente, data, itens = extrair_pedido("temp_pedido.pdf")
                salvar_pedido(cliente, data, itens)

                st.success(f"Pedido importado com sucesso ({len(itens)} itens)")

                st.subheader("Cliente")
                st.json(cliente)

                st.subheader("Itens")
                st.table(itens)

            except Exception as e:
                st.error(f"Erro ao importar pedido: {e}")

# ---------- JORNAL PDF ----------
elif st.session_state.tela == "jornal":
    st.header("📰 Importar Jornal de Ofertas (PDF)")

    arquivo = st.file_uploader("Selecione o jornal em PDF", type=["pdf"])
    validade = st.text_input("Validade (ex: 23/01/2026)")
    edicao = st.text_input("Edição do Jornal")

    if st.button("🚀 Processar Jornal", use_container_width=True):

        if not arquivo:
            st.warning("Selecione um PDF antes de processar.")
        elif not validade:
            st.warning("Informe a validade do jornal.")
        else:
            try:
                with open("temp_jornal.pdf", "wb") as f:
                    f.write(arquivo.read())

                ofertas = extrair_jornal("temp_jornal.pdf", validade, edicao)
                salvar_ofertas(ofertas)

                st.success(f"{len(ofertas)} ofertas importadas c
