import streamlit as st
from motor_extracao import (
    extrair_jornal,
    extrair_pedido,
    salvar_ofertas,
    salvar_pedido
)

st.set_page_config(layout="wide")
st.title("📊 CRM Representante Comercial")

# ================= ESTADO DE NAVEGAÇÃO =================

if "tela" not in st.session_state:
    st.session_state.tela = "home"

def ir(tela):
    st.session_state.tela = tela

# ================= BARRA PRINCIPAL =================

st.markdown("### Menu Principal")

col1, col2, col3 = st.columns(3)

with col1:
    st.button("📥 Pedido PDF", use_container_width=True, on_click=ir, args=("pedido",))

with col2:
    st.button("📰 Jornal PDF", use_container_width=True, on_click=ir, args=("jornal",))

with col3:
    st.button("📈 Cruzamento", use_container_width=True, on_click=ir, args=("cruzamento",))

col4, col5, col6 = st.columns(3)

with col4:
    st.button("📂 Histórico", use_container_width=True, on_click=ir, args=("historico",))

with col5:
    st.button("📊 Relatórios", use_container_width=True, on_click=ir, args=("relatorios",))

with col6:
    st.button("🚨 Alertas", use_container_width=True, on_click=ir, args=("alertas",))

st.divider()

# ================= TELAS =================

# ---------- HOME ----------
if st.session_state.tela == "home":
    st.info("Selecione uma função acima.")

# ---------- PEDIDO ----------
elif st.session_state.tela == "pedido":
    st.header("📥 Importar Pedido em PDF")

    arquivo = st.file_uploader("Selecione o pedido em PDF", type=["pdf"])

    if st.button("🚀 Processar Pedido", use_container_width=True) and arquivo:
        with open("temp_pedido.pdf", "wb") as f:
            f.write(arquivo.read())

        cliente, data, itens = extrair_pedido("temp_pedido.pdf")
        salvar_pedido(cliente, data, itens)

        st.success(f"Pedido importado com sucesso ({len(itens)} itens)")

        st.subheader("Cliente")
        st.json(cliente)

        st.subheader("Itens")
        st.table(itens)

# ---------- JORNAL ----------
elif st.session_state.tela == "jornal":
    st.header("📰 Importar Jornal de Ofertas (PDF)")

    arquivo = st.file_uploader("Selecione o jornal em PDF", type=["pdf"])
    validade = st.text_input("Validade (ex: 23/01/2026)")
    edicao = st.text_input("Edição do Jornal")

    if st.button("🚀 Processar Jornal", use_container_width=True) and arquivo:
        with open("temp_jornal.pdf", "wb") as f:
            f.write(arquivo.read())

        ofertas = extrair_jornal("temp_jornal.pdf", validade, edicao)
        salvar_ofertas(ofertas)

        st.success(f"{len(ofertas)} ofertas importadas com sucesso!")

# ---------- DEMAIS ----------

elif st.session_state.tela == "cruzamento":
    st.info("Módulo de cruzamento em desenvolvimento")

elif st.session_state.tela == "historico":
    st.info("Módulo de histórico em desenvolvimento")

elif st.session_state.tela == "relatorios":
    st.info("Módulo de relatórios em desenvolvimento")

elif st.session_state.tela == "alertas":
    st.info("Módulo de alertas em desenvolvimento")
