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
    texto_puro = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto_puro += page.extract_text() + "\n"

    # 1. Nome do Cliente
    cliente = "Cliente"
    if "Nome Fantasia:" in texto_puro:
        cliente = texto_puro.split("Nome Fantasia:")[1].split("\n")[0].strip()
    
    # 2. Telefone Real (Número do Cliente)
    telefone = ""
    if "Fone:" in texto_puro:
        # Extrai apenas os números do campo fone
        fone_raw = texto_puro.split("Fone:")[1].split("\n")[0].strip()
        telefone = "".join(re.findall(r'\d+', fone_raw))
        if telefone and not telefone.startswith("55"):
            telefone = "55" + telefone

    # 3. LEITURA FLEXÍVEL DE PRODUTOS
    dados_finais = []
    linhas = texto_puro.split('\n')
    
    for linha in linhas:
        partes = linha.split()
        # Se a linha começa com número (SKU) e tem pelo menos 4 partes (SKU, Nome, Un, Preço)
        if len(partes) >= 4 and partes[0].isdigit():
            sku = partes[0]
            
            # Procuramos o preço unitário (valor com vírgula, geralmente no final)
            # Vamos varrer a linha de trás para frente para achar o valor real pago
            preco_limpo = None
            for p in reversed(partes):
                if "," in p and p.replace(',', '').replace('.', '').isdigit():
                    try:
                        preco_limpo = float(p.replace('.', '').replace(',', '.'))
                        break # Achou o primeiro valor com vírgula da direita para a esquerda
                    except:
                        continue
            
            if preco_limpo:
                # O nome é o que sobra entre o SKU e os dados técnicos
                nome = " ".join(partes[1:-4]) 
                dados_finais.append([sku, nome, preco_limpo, cliente, telefone])

    if not dados_finais:
        return None
    return pd.DataFrame(dados_finais, columns=['SKU', 'Produto', 'Preço_Pago', 'Nome_Cliente', 'Telefone'])

# --- INTERFACE ---
aba1, aba2 = st.tabs(["📥 Alimentar Histórico", "💰 Gerar Ofertas"])

with aba1:
    st.header("Upload do Pedido")
    arquivo = st.file_uploader("Suba o PDF do Pedido", type="pdf")
    if arquivo:
        dados = extrair_dados_pedido(arquivo)
        if dados is not None:
            st.success(f"✅ Identificado: {dados['Nome_Cliente'].iloc[0]}")
            st.write(f"📞 WhatsApp do Cliente: {dados['Telefone'].iloc[0]}")
            st.table(dados[['SKU', 'Produto', 'Preço_Pago']])
            if st.button("SALVAR NO HISTÓRICO"):
                if os.path.exists(HISTORICO_PATH):
                    antigo = pd.read_csv(HISTORICO_PATH, dtype={'SKU': str})
                    novo = pd.concat([antigo, dados]).drop_duplicates(subset=['SKU', 'Preço_Pago'])
                    novo.to_csv(HISTORICO_PATH, index=False)
                else:
                    dados.to_csv(HISTORICO_PATH, index=False)
                st.balloons()
                st.success("Histórico atualizado! Dados guardados para os próximos 6 meses.")
        else:
            st.error("ERRO: Não encontrei produtos. Verifique se o PDF tem texto selecionável.")

with aba2:
    st.header("Cruzamento de Ofertas")
    jornal = st.file_uploader("Suba o Jornal (MATRIZ)", type="pdf")
    if jornal and os.path.exists(HISTORICO_PATH):
        with pdfplumber.open(jornal) as pdf:
            txt_jornal = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        
        hist = pd.read_csv(HISTORICO_PATH, dtype={'SKU': str})
        ofertas_list = []
        
        for _, row in hist.iterrows():
            sku_busca = str(row['SKU'])
            if sku_busca in txt_jornal:
                # Procura a linha que contém o código no jornal
                for l_jornal in txt_jornal.split('\n'):
                    if l_jornal.startswith(sku_busca):
                        # Pega o último preço com vírgula da linha do jornal
                        precos_j = re.findall(r"(\d+,\d{2,4})", l_jornal)
                        if precos_j:
                            valor_j = float(precos_j[-1].replace(',', '.'))
                            if valor_j < row['Preço_Pago']:
                                ofertas_list.append([row['SKU'], row['Produto'], row['Preço_Pago'], valor_j, row['Nome_Cliente'], row['Telefone']])
        
        if ofertas_list:
            df_of = pd.DataFrame(ofertas_list, columns=['SKU', 'Produto', 'Antigo', 'Novo', 'Cliente', 'WhatsApp'])
            st.write(f"### 🔥 Ofertas para {df_of['Cliente'].iloc[0]}")
            st.table(df_of[['Produto', 'Antigo', 'Novo']])
            
            msg = f"Olá, *{df_of['Cliente'].iloc[0]}*! Itens que você compra entraram em oferta:\n\n"
            for _, r in df_of.iterrows():
                msg += f"✅ *{r['Produto']}*\nDe: R${r['Antigo']:.2f} por *R${r['Novo']:.2f}*\n\n"
            
            link = f"https://api.whatsapp.com/send?phone={df_of['WhatsApp'].iloc[0]}&text={urllib.parse.quote(msg)}"
            st.markdown(f"## [👉 ENVIAR PARA WHATSAPP REAL]({link})")
        else:
            st.info("Nenhuma oferta menor que o histórico foi encontrada.")
