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
    tabelas_extraidas = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto_completo += page.extract_text() + "\n"
            # Tenta extrair tabelas desenhadas no PDF
            table = page.extract_table()
            if table:
                tabelas_extraidas.extend(table)

    # 1. Tenta pegar o nome do cliente
    cliente_match = re.search(r"(?:Nome Fantasia|Cliente):\s*(.*)", texto_completo, re.IGNORECASE)
    nome_cliente = cliente_match.group(1).strip() if cliente_match else "Cliente Avulso"
    
    # 2. Tenta pegar o telefone
    fone_match = re.search(r"(?:Fone|Tel|Celular):\s*\(?(\d{2})\)?\s*(\d{4,5}-?\d{4})", texto_completo)
    telefone = f"55{fone_match.group(1)}{fone_match.group(2)}".replace("-","").replace(" ","") if fone_match else "55"

    # 3. Super Leitor de Itens (Procura por: Código + Nome + Valores)
    # Procura padrão: 5 dígitos + Espaço + Texto + Valor com vírgula no final
    dados_finais = []
    
    # Tenta ler linha por linha do texto
    for linha in texto_completo.split('\n'):
        # Procura por linhas que começam com o código do produto (Ex: 37050)
        match = re.search(r"^(\d{4,6})\s+(.*?)\s+[\d,]+\s+[\d,]+\s+\w{2}\s+[\d,]+\s+([\d,]+)", linha)
        if match:
            sku, nome, preco = match.groups()
            preco_limpo = float(preco.replace('.', '').replace(',', '.'))
            dados_finais.append([sku, nome, preco_limpo, nome_cliente, telefone])

    if not dados_finais:
        return None

    return pd.DataFrame(dados_finais, columns=['SKU', 'Produto', 'Preço_Pago', 'Nome_Cliente', 'Telefone'])

def extrair_jornal(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    # Padrão para o Catálogo Depecil: Código + Descrição + Preço Promo
    padrao_jornal = r"(\d{4,6})\s+([A-Z\s\d\.]{5,})\s+[\d\(\)\s]+([\d,]{2,})"
    itens = re.findall(padrao_jornal, texto)
    df_jornal = pd.DataFrame(itens, columns=['SKU', 'Produto_Jornal', 'Preço_Oferta'])
    df_jornal['Preço_Oferta'] = df_jornal['Preço_Oferta'].str.replace(',', '.').astype(float)
    df_jornal['SKU'] = df_jornal['SKU'].astype(str).str.strip()
    return df_jornal

# --- INTERFACE ---
aba1, aba2 = st.tabs(["📥 Alimentar Histórico", "💰 Gerar Ofertas"])

with aba1:
    st.header("Upload do Pedido")
    arquivo_pedido = st.file_uploader("Suba o PDF do Pedido (Depecil)", type="pdf")
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
                st.success("Dados salvos! Vá para a aba 'Gerar Ofertas'.")
        else:
            st.error("⚠️ O leitor não identificou os produtos. Verifique se o PDF está nítido.")

with aba2:
    st.header("Cruzamento de Ofertas")
    arquivo_jornal = st.file_uploader("Suba o Catálogo (MATRIZ)", type="pdf")
    if arquivo_jornal:
        if os.path.exists(HISTORICO_PATH):
            df_jornal = extrair_jornal(arquivo_jornal)
            df_hist = pd.read_csv(HISTORICO_PATH, dtype={'SKU': str})
            cruzado = pd.merge(df_jornal, df_hist, on="SKU")
            ofertas = cruzado[cruzado['Preço_Oferta'] < cruzado['Preço_Pago']].drop_duplicates(subset=['SKU'])
            
            if not ofertas.empty:
                st.write(f"### 🔥 {len(ofertas)} Ofertas Encontradas!")
                cliente = ofertas['Nome_Cliente'].iloc[0]
                tel = st.text_input("Confirmar Telefone", ofertas['Telefone'].iloc[0])
                msg = f"Olá, *{cliente}*! 👋\n\nEstes itens que você costuma comprar baixaram de preço no jornal de hoje:\n\n"
                for _, r in ofertas.iterrows():
                    msg += f"✅ *{r['Produto_Jornal'].strip()}*\nDe: R${r['Preço_Pago']:.2f} por *R${r['Preço_Oferta']:.2f}*\n\n"
                link = f"https://api.whatsapp.com/send?phone={tel}&text={urllib.parse.quote(msg)}"
                st.markdown(f'## [👉 CLIQUE AQUI PARA ENVIAR WHATSAPP]({link})')
            else:
                st.info("Nenhuma oferta hoje é melhor que o preço pago anteriormente.")
        else:
            st.warning("Primeiro, suba um pedido na aba 'Alimentar Histórico'.")
