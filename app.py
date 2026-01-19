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
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto_completo += page.extract_text() + "\n"

    # Captura Nome do Cliente (mais flexível)
    cliente_match = re.search(r"(?:Nome Fantasia|Razão Social|Cliente):\s*(.*)", texto_completo, re.IGNORECASE)
    nome_cliente = cliente_match.group(1).strip() if cliente_match else "Cliente"
    
    # Captura Telefone
    fone_match = re.search(r"(?:Fone|Tel|Cel):\s*(\d+)", texto_completo, re.IGNORECASE)
    telefone = fone_match.group(1) if fone_match else "55"

    # NOVO MOTOR DE BUSCA: Procura por qualquer sequência de 5 dígitos + nome + preço
    dados_finais = []
    linhas = texto_completo.split('\n')
    for linha in linhas:
        # Regex que procura: 5 dígitos -> Nome (texto) -> Qualquer coisa -> Valor com vírgula (ex: 31,62)
        match = re.search(r"(\d{5})\s+(.*?)\s+.*?([\d,]+)$", linha)
        if match:
            sku, nome, preco = match.groups()
            try:
                # Limpa o preço (remove pontos de milhar e troca vírgula por ponto)
                preco_limpo = float(preco.replace('.', '').replace(',', '.'))
                if preco_limpo > 0:
                    dados_finais.append([sku, nome.strip(), preco_limpo, nome_cliente, telefone])
            except:
                continue

    if not dados_finais:
        # Tentativa secundária: Procura apenas SKU e Preço se a primeira falhar
        matches_simples = re.findall(r"(\d{5})\s+.*?([\d,]+)$", texto_completo, re.MULTILINE)
        for sku, preco in matches_simples:
            try:
                preco_limpo = float(preco.replace('.', '').replace(',', '.'))
                dados_finais.append([sku, "Produto " + sku, preco_limpo, nome_cliente, telefone])
            except: continue

    return pd.DataFrame(dados_finais, columns=['SKU', 'Produto', 'Preço_Pago', 'Nome_Cliente', 'Telefone']) if dados_finais else None

def extrair_jornal(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    # Procura códigos de 5 ou mais dígitos e preços
    itens = re.findall(r"(\d{5,})\s+(.*?)\s+.*?([\d,]{2,})$", texto, re.MULTILINE)
    df = pd.DataFrame(itens, columns=['SKU', 'Produto_Jornal', 'Preço_Oferta'])
    df['Preço_Oferta'] = df['Preço_Oferta'].str.replace('.', '').str.replace(',', '.').astype(float)
    df['SKU'] = df['SKU'].astype(str).str.strip()
    return df

# --- INTERFACE ---
tab1, tab2 = st.tabs(["📥 Alimentar Histórico", "💰 Gerar Ofertas"])

with tab1:
    st.header("Upload do Pedido")
    arquivo_pedido = st.file_uploader("Escolha o PDF", type="pdf")
    if arquivo_pedido:
        dados = extrair_dados_pedido(arquivo_pedido)
        if dados is not None and not dados.empty:
            st.success(f"✅ Identificado: {dados['Nome_Cliente'].iloc[0]}")
            st.dataframe(dados)
            if st.button("Salvar no Histórico"):
                if os.path.exists(HISTORICO_PATH):
                    hist = pd.read_csv(HISTORICO_PATH, dtype={'SKU': str})
                    df_final = pd.concat([hist, dados]).drop_duplicates(subset=['SKU', 'Preço_Pago'])
                else:
                    df_final = dados
                df_final.to_csv(HISTORICO_PATH, index=False)
                st.balloons()
        else:
            st.error("⚠️ Não conseguimos ler os produtos. O PDF pode ser uma imagem ou o formato mudou.")

with tab2:
    st.header("Cruzamento com Jornal")
    arquivo_jornal = st.file_uploader("Suba o Jornal", type="pdf")
    if arquivo_jornal and os.path.exists(HISTORICO_PATH):
        df_j = extrair_jornal(arquivo_jornal)
        df_h = pd.read_csv(HISTORICO_PATH, dtype={'SKU': str})
        cruzado = pd.merge(df_j, df_h, on="SKU")
        ofertas = cruzado[cruzado['Preço_Oferta'] < cruzado['Preço_Pago']].drop_duplicates(subset=['SKU'])
        if not ofertas.empty:
            st.write(f"### 🔥 {len(ofertas)} Ofertas!")
            cliente = ofertas['Nome_Cliente'].iloc[0]
            tel = st.text_input("WhatsApp:", ofertas['Telefone'].iloc[0])
            msg = f"Olá, *{cliente}*! 👋\n\nEstes itens baixaram de preço:\n\n"
            for _, r in ofertas.iterrows():
                msg += f"✅ *{r['Produto_Jornal']}*\nDe: R${r['Preço_Pago']:.2f} por *R${r['Preço_Oferta']:.2f}*\n\n"
            link = f"https://api.whatsapp.com/send?phone={tel}&text={urllib.parse
