import streamlit as st
import pandas as pd
import pdfplumber
import re
import urllib.parse
from datetime import datetime
import os

# Configuração da página
st.set_page_config(page_title="AM Representações CRM", layout="wide")

st.title("🚀 AM Representações - CRM de Vendas")

# O Streamlit lida com arquivos de forma diferente. Vamos usar o cache para o histórico.
HISTORICO_PATH = "historico_vendas.csv"

# --- FUNÇÕES DE EXTRAÇÃO ---
def extrair_dados_pedido(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    
    cliente_match = re.search(r"Nome Fantasia:\s*(.*)", texto)
    nome_cliente = cliente_match.group(1).strip() if cliente_match else "Cliente"
    
    fone_match = re.search(r"(?:Fone|Tel|Celular):\s*\(?(\d{2})\)?\s*(\d{4,5}-?\d{4})", texto)
    telefone = f"55{fone_match.group(1)}{fone_match.group(2)}".replace("-","").replace(" ","") if fone_match else ""

    padrao_itens = r"(\d{4,})\s+(.*?)\s+[\d,]+\s+[\d,]+\s+\w{2}\s+[\d,]+\s+([\d,]+)"
    itens = re.findall(padrao_itens, texto)
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
    df = pd.DataFrame(itens, columns=['SKU', 'Produto_Jornal', 'Preço_Oferta'])
    df['Preço_Oferta'] = df['Preço_Oferta'].str.replace(',', '.').astype(float)
    df['SKU'] = df['SKU'].astype(str).str.strip()
    return df

# --- INTERFACE ---
aba1, aba2 = st.tabs(["📥 Alimentar Histórico (Pedido)", "💰 Gerar Ofertas (Jornal)"])

with aba1:
    st.header("Upload do Pedido")
    arquivo_pedido = st.file_uploader("Arraste o PDF do Pedido aqui", type="pdf")
    if arquivo_pedido:
        dados_pedido = extrair_dados_pedido(arquivo_pedido)
        st.write(f"**Cliente:** {dados_pedido['Nome_Cliente'].iloc[0]}")
        if st.button("Salvar no Histórico"):
            if os.path.exists(HISTORICO_PATH):
                hist = pd.read_csv(HISTORICO_PATH, dtype={'SKU': str})
                df_final = pd.concat([hist, dados_pedido]).drop_duplicates(subset=['SKU', 'Preço_Pago'])
            else:
                df_final = dados_pedido
            df_final.to_csv(HISTORICO_PATH, index=False)
            st.success("✅ Histórico atualizado com sucesso!")

with aba2:
    st.header("Cruzamento de Ofertas")
    arquivo_jornal = st.file_uploader("Arraste o PDF do Jornal (MATRIZ) aqui", type="pdf")
    
    if arquivo_jornal and os.path.exists(HISTORICO_PATH):
        df_jornal = extrair_jornal(arquivo_jornal)
        df_hist = pd.read_csv(HISTORICO_PATH, dtype={'SKU': str})
        
        cruzado = pd.merge(df_jornal, df_hist, on="SKU")
        ofertas = cruzado[cruzado['Preço_Oferta'] < cruzado['Preço_Pago']].drop_duplicates(subset=['SKU'])
        
        if not ofertas.empty:
            st.write(f"### 🔥 Encontramos {len(ofertas)} ofertas!")
            cliente = ofertas['Nome_Cliente'].iloc[0]
            tel = st.text_input("Confirmar Telefone (com DDD)", ofertas['Telefone'].iloc[0])
            
            # Montar mensagem
            msg = f"Olá, *{cliente}*! 👋\n\nVi que estes itens baixaram de preço:\n\n"
            for _, r in ofertas.iterrows():
                msg += f"✅ *{r['Produto_Jornal'].strip()}*\nDe: R${r['Preço_Pago']:.2f} por *R${r['Preço_Oferta']:.2f}*\n\n"
            
            if st.button("Gerar Link do WhatsApp"):
                link = f"https://api.whatsapp.com/send?phone={tel}&text={urllib.parse.quote(msg)}"
                st.markdown(f'[**CLIQUE AQUI PARA ENVIAR WHATSAPP**]({link})')
                st.info("O link abrirá o WhatsApp com a mensagem pronta.")
        else:
            st.warning("Nenhuma oferta melhor que o preço histórico foi encontrada.")
