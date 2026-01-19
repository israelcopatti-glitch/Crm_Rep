import streamlit as st
import pandas as pd
import pdfplumber
import re
import urllib.parse
import os

st.set_page_config(page_title="AM CRM", layout="wide")
st.title("🚀 AM Representações - CRM")

HISTORICO_PATH = "historico_vendas.csv"

def extrair_dados_pedido(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        primeira_pagina = pdf.pages[0]
        texto_completo = primeira_pagina.extract_text()
        # Extração por tabela (mais robusto para o layout Depecil)
        tabela = primeira_pagina.extract_table()

    # 1. Captura Nome Fantasia e Telefone no texto do cabeçalho
    cliente_match = re.search(r"Nome Fantasia:\s*(.*)", texto_completo)
    nome_cliente = cliente_match.group(1).strip() if cliente_match else "Cliente"
    
    fone_match = re.search(r"Fone:\s*(\d+)", texto_completo)
    telefone = fone_match.group(1) if fone_match else ""

    # 2. Processamento da Tabela
    dados_finais = []
    if tabela:
        for linha in tabela:
            # Procuramos a linha que tem o código do produto (geralmente 5 dígitos) na primeira coluna
            if linha[0] and linha[0].isdigit() and len(linha[0]) >= 4:
                sku = linha[0]
                nome = linha[1]
                # O valor unitário no seu PDF é a penúltima coluna (índice -2 ou 6)
                preco_texto = linha[-2] if linha[-2] else "0"
                
                try:
                    # Limpa o valor (ex: 31,6236 -> 31.62)
                    preco_limpo = float(preco_texto.replace('.', '').replace(',', '.'))
                    if preco_limpo > 0:
                        dados_finais.append([sku, nome, preco_limpo, nome_cliente, telefone])
                except:
                    continue

    # Se a extração por tabela falhar, usamos o motor de busca de texto como backup
    if not dados_finais:
        for linha in texto_completo.split('\n'):
            match = re.search(r"(\d{5,})\s+(.*?)\s+[\d,]+\s+[\d,]+\s+\w{2}\s+[\d,]+\s+([\d,]+)", linha)
            if match:
                sku, nome, preco = match.groups()
                preco_limpo = float(preco.replace('.', '').replace(',', '.'))
                dados_finais.append([sku, nome.strip(), preco_limpo, nome_cliente, telefone])

    if not dados_finais:
        return None
    return pd.DataFrame(dados_finais, columns=['SKU', 'Produto', 'Preço_Pago', 'Nome_Cliente', 'Telefone'])

def extrair_jornal(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    itens = re.findall(r"(\d{5,})\s+(.*?)\s+.*?([\d,]{2,})$", texto, re.MULTILINE)
    df = pd.DataFrame(itens, columns=['SKU', 'Produto_Jornal', 'Preço_Oferta'])
    df['Preço_Oferta'] = df['Preço_Oferta'].str.replace('.', '').str.replace(',', '.').astype(float)
    df['SKU'] = df['SKU'].astype(str).str.strip()
    return df

# --- INTERFACE ---
tab1, tab2 = st.tabs(["📥 Alimentar Histórico", "💰 Gerar Ofertas"])

with tab1:
    st.header("Upload do Pedido (Depecil)")
    arquivo_pedido = st.file_uploader("Suba o PDF do Pedido", type="pdf")
    if arquivo_pedido:
        dados = extrair_dados_pedido(arquivo_pedido)
        if dados is not None:
            st.success(f"✅ Pedido de: {dados['Nome_Cliente'].iloc[0]}")
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
            st.error("O sistema não encontrou os itens. O PDF pode ser uma imagem protegida.")

with tab2:
    st.header("Cruzamento de Ofertas")
    arquivo_jornal = st.file_uploader("Suba o PDF do Jornal (MATRIZ)", type="pdf")
    if arquivo_jornal and os.path.exists(HISTORICO_PATH):
        df_j = extrair_jornal(arquivo_jornal)
        df_h = pd.read_csv(HISTORICO_PATH, dtype={'SKU': str})
        cruzado = pd.merge(df_j, df_h, on="SKU")
        ofertas = cruzado[cruzado['Preço_Oferta'] < cruzado['Preço_Pago']].drop_duplicates(subset=['SKU'])
        if not ofertas.empty:
            st.write(f"### 🔥 Encontramos {len(ofertas)} Ofertas!")
            cliente = ofertas['Nome_Cliente'].iloc[0]
            tel = st.text_input("Confirmar WhatsApp:", ofertas['Telefone'].iloc[0])
            msg = f"Olá, *{cliente}*! 👋\n\nEstes itens baixaram de preço:\n\n"
            for _, r in ofertas.iterrows():
                msg += f"✅ *{r['Produto_Jornal']}*\nDe: R${r['Preço_Pago']:.2f} por *R${r['Preço_Oferta']:.2f}*\n\n"
            link = f"https://api.whatsapp.com/send?phone={tel}&text={urllib.parse.quote(msg)}"
            st.markdown(f'## [👉 ENVIAR WHATSAPP]({link})')
        else:
            st.info("Nenhuma oferta melhor encontrada.")
