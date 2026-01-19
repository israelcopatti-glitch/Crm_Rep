import streamlit as st
import pandas as pd
import pdfplumber
import re
import urllib.parse
from datetime import datetime
import os

st.set_page_config(page_title="AM Representações CRM", layout="wide")
st.title("🚀 AM Representações - CRM")

HISTORICO_PATH = "historico_vendas.csv"

def extrair_dados_pedido(pdf_file):
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto_completo += page.extract_text() + "\n"

    # Busca Nome Fantasia e Telefone
    cliente_match = re.search(r"Nome Fantasia:\s*(.*)", texto_completo)
    nome_cliente = cliente_match.group(1).strip() if cliente_match else "Cliente"
    
    fone_match = re.search(r"Fone:\s*(\d+)", texto_completo)
    telefone = fone_match.group(1) if fone_match else "55"

    # Busca Itens: Código (5 dígitos) + Nome + V. Unit (penúltima coluna)
    dados_finais = []
    for linha in texto_completo.split('\n'):
        # Procura linhas que começam com o código do produto
        match = re.search(r"(\d{5})\s+(.*?)\s+[\d,]+\s+[\d,]+\s+\w{2}\s+[\d,]+\s+([\d,]+)", linha)
        if match:
            sku, nome, preco = match.groups()
            preco_limpo = float(preco.replace(',', '.'))
            dados_finais.append([sku, nome, preco_limpo, nome_cliente, telefone])

    return pd.DataFrame(dados_finais, columns=['SKU', 'Produto', 'Preço_Pago', 'Nome_Cliente', 'Telefone']) if dados_finais else None

def extrair_jornal(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto = "\n".join([page.extract_text() for page in pdf.pages])
    # Padrão Jornal Depecil: Código + Descrição + Preço
    padrao = r"(\d{5,})\s+([A-Z\s\d\.]{5,})\s+[\d\(\)\s]+([\d,]{2,})"
    itens = re.findall(padrao, texto)
    df = pd.DataFrame(itens, columns=['SKU', 'Produto_Jornal', 'Preço_Oferta'])
    df['Preço_Oferta'] = df['Preço_Oferta'].str.replace(',', '.').astype(float)
    df['SKU'] = df['SKU'].astype(str).str.strip()
    return df

# --- INTERFACE ---
tab1, tab2 = st.tabs(["📥 Alimentar Histórico", "💰 Gerar Ofertas"])

with tab1:
    st.header("Upload do Pedido (Depecil)")
    arquivo_pedido = st.file_uploader("Escolha o PDF do Pedido", type="pdf")
    if arquivo_pedido:
        dados = extrair_dados_pedido(arquivo_pedido)
        if dados is not None:
            st.success(f"✅ Pedido identificado: {dados['Nome_Cliente'].iloc[0]}")
            st.dataframe(dados[['SKU', 'Produto', 'Preço_Pago']])
            if st.button("Salvar no Histórico"):
                if os.path.exists(HISTORICO_PATH):
                    hist = pd.read_csv(HISTORICO_PATH, dtype={'SKU': str})
                    df_final = pd.concat([hist, dados]).drop_duplicates(subset=['SKU', 'Preço_Pago'])
                else:
                    df_final = dados
                df_final.to_csv(HISTORICO_PATH, index=False)
                st.balloons()
        else:
            st.error("Erro ao ler itens. Verifique se o PDF é um pedido Depecil original.")

with tab2:
    st.header("Cruzamento com Jornal")
    arquivo_jornal = st.file_uploader("Suba o PDF da MATRIZ JORNAL", type="pdf")
    if arquivo_jornal and os.path.exists(HISTORICO_PATH):
        df_jornal = extrair_jornal(arquivo_jornal)
        df_hist = pd.read_csv(HISTORICO_PATH, dtype={'SKU': str})
        cruzado = pd.merge(df_jornal, df_hist, on="SKU")
        ofertas = cruzado[cruzado['Preço_Oferta'] < cruzado['Preço_Pago']].drop_duplicates(subset=['SKU'])
        if not ofertas.empty:
            cliente = ofertas['Nome_Cliente'].iloc[0]
            tel = st.text_input("Telefone:", ofertas['Telefone'].iloc[0])
            msg = f"Olá, *{cliente}*! 👋\n\nEstes itens que você compra baixaram de preço hoje:\n\n"
            for _, r in ofertas.iterrows():
                msg += f"✅ *{r['Produto_Jornal'].strip()}*\nDe: R${r['Preço_Pago']:.2f} por *R${r['Preço_Oferta']:.2f}*\n\n"
            link = f"https://api.whatsapp.com/send?phone={tel}&text={urllib.parse.quote(msg)}"
            st.markdown(f'### [👉 ENVIAR PARA WHATSAPP]({link})')
