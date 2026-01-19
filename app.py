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
    with pdfplumber.open(pdf_file) as pdf:
        texto = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    
    # Busca o Cliente com mais flexibilidade
    cliente_match = re.search(r"(?:Nome Fantasia|Cliente):\s*(.*)", texto, re.IGNORECASE)
    nome_cliente = cliente_match.group(1).strip() if cliente_match else "Cliente Avulso"
    
    fone_match = re.search(r"(?:Fone|Tel|Celular):\s*\(?(\d{2})\)?\s*(\d{4,5}-?\d{4})", texto)
    telefone = f"55{fone_match.group(1)}{fone_match.group(2)}".replace("-","").replace(" ","") if fone_match else "55"

    # Captura itens: Código + Nome + V. Unit (Suporta o layout Depecil)
    padrao_itens = r"(\d{4,})\s+(.*?)\s+[\d,]+\s+[\d,]+\s+\w{2}\s+[\d,]+\s+([\d,]+)"
    itens = re.findall(padrao_itens, texto)
    
    if not itens:
        return None

    df = pd.DataFrame(itens, columns=['SKU', 'Produto', 'Preço_Pago'])
    df['Preço_Pago'] = df['Preço_Pago'].str.replace(',', '.').astype(float)
    df['SKU'] = df['SKU'].astype(str).str.strip()
    df['Nome_Cliente'] = nome_cliente
    df['Telefone'] = telefone
    return df

def extrair_jornal(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    padrao_jornal = r"(\d{4,})\s+([A-Z\s\d\.]{5,})\s+[\d\(\)\s]+([\d,]{2,})"
    itens = re.findall(padrao_jornal, texto)
    df_jornal = pd.DataFrame(itens, columns=['SKU', 'Produto_Jornal', 'Preço_Oferta'])
    df_jornal['Preço_Oferta'] = df_jornal['Preço_Oferta'].str.replace(',', '.').astype(float)
    df_jornal['SKU'] = df_jornal['SKU'].astype(str).str.strip()
    return df_jornal

aba1, aba2 = st.tabs(["📥 Alimentar Histórico", "💰 Gerar Ofertas"])

with aba1:
    st.header("Upload do Pedido")
    arquivo_pedido = st.file_uploader("Suba o PDF do Pedido", type="pdf")
    if arquivo_pedido:
        dados = extrair_dados_pedido(arquivo_pedido)
        if dados is not None:
            st.success(f"✅ Pedido de: {dados['Nome_Cliente'].iloc[0]}")
            st.table(dados[['SKU', 'Produto', 'Preço_Pago']])
            if st.button("Salvar no Histórico"):
                if os.path.exists(HISTORICO_PATH):
                    hist = pd.read_csv(HISTORICO_PATH, dtype={'SKU': str})
                    df_final = pd.concat([hist, dados]).drop_duplicates(subset=['SKU', 'Preço_Pago'])
                else:
                    df_final = dados
                df_final.to_csv(HISTORICO_PATH, index=False)
                st.balloons()
        else:
            st.error("Não foi possível ler os itens deste PDF. Verifique o formato.")

with aba2:
    st.header("Cruzamento de Ofertas")
    arquivo_jornal = st.file_uploader("Suba o Jornal (MATRIZ)", type="pdf")
    if arquivo_jornal and os.path.exists(HISTORICO_PATH):
        df_jornal = extrair_jornal(arquivo_jornal)
        df_hist = pd.read_csv(HISTORICO_PATH, dtype={'SKU': str})
        cruzado = pd.merge(df_jornal, df_hist, on="SKU")
        ofertas = cruzado[cruzado['Preço_Oferta'] < cruzado['Preço_Pago']].drop_duplicates(subset=['SKU'])
        if not ofertas.empty:
            cliente = ofertas['Nome_Cliente'].iloc[0]
            tel = st.text_input("Confirmar Telefone", ofertas['Telefone'].iloc[0])
            msg = f"Olá, *{cliente}*! 👋\n\nEstes itens que você compra baixaram de preço:\n\n"
            for _, r in ofertas.iterrows():
                msg += f"✅ *{r['Produto_Jornal'].strip()}*\nDe: R${r['Preço_Pago']:.2f} por *R${r['Preço_Oferta']:.2f}*\n\n"
            link = f"https://api.whatsapp.com/send?phone={tel}&text={urllib.parse.quote(msg)}"
            st.markdown(f'### [👉 ENVIAR WHATSAPP]({link})')
        else:
            st.info("Nenhuma oferta encontrada para os itens do histórico.")
