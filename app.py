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

    # 1. Captura Nome Fantasia e Telefone (Padrão Depecil)
    cliente_match = re.search(r"Nome Fantasia:\s*(.*)", texto_completo)
    nome_cliente = cliente_match.group(1).strip() if cliente_match else "Cliente"
    
    fone_match = re.search(r"Fone:\s*(\d+)", texto_completo)
    # Garante que usamos o número real do cliente conforme solicitado
    telefone = fone_match.group(1) if fone_match else ""

    # 2. Captura de Itens (Focado no seu print da Depecil)
    # O padrão busca: Código (ex: 37050) + Nome do Produto + Un + Qtde + Valor Unitário
    dados_finais = []
    linhas = texto_completo.split('\n')
    
    for linha in linhas:
        # Padrão: SKU(5 dígitos) | Descrição | % IPI | % ICMS | Un | Qtde | V.Unit (com vírgula)
        match = re.search(r"(\d{5,})\s+(.*?)\s+[\d,]+\s+[\d,]+\s+\w{2}\s+[\d,]+\s+([\d,]+)", linha)
        if match:
            sku, nome, preco = match.groups()
            # Limpa o preço (ex: 31,6236 vira 31.62)
            preco_limpo = float(preco.replace(',', '.'))
            dados_finais.append([sku, nome.strip(), preco_limpo, nome_cliente, telefone])

    if not dados_finais:
        return None
    return pd.DataFrame(dados_finais, columns=['SKU', 'Produto', 'Preço_Pago', 'Nome_Cliente', 'Telefone'])

def extrair_jornal(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    # Padrão flexível para o jornal de ofertas
    itens = re.findall(r"(\d{5,})\s+(.*?)\s+.*?([\d,]{2,})$", texto, re.MULTILINE)
    df = pd.DataFrame(itens, columns=['SKU', 'Produto_Jornal', 'Preço_Oferta'])
    df['Preço_Oferta'] = df['Preço_Oferta'].str.replace('.', '').str.replace(',', '.').astype(float)
    df['SKU'] = df['SKU'].astype(str).str.strip()
    return df

# --- INTERFACE STREAMLIT ---
tab1, tab2 = st.tabs(["📥 Alimentar Histórico", "💰 Gerar Ofertas"])

with tab1:
    st.header("Upload do Pedido (Depecil)")
    arquivo_pedido = st.file_uploader("Suba o PDF do Pedido", type="pdf")
    if arquivo_pedido:
        dados = extrair_dados_pedido(arquivo_pedido)
        if dados is not None:
            st.success(f"✅ Pedido de: {dados['Nome_Cliente'].iloc[0]}")
            st.dataframe(dados[['SKU', 'Produto', 'Preço_Pago']])
            
            # Manter histórico sem perder dados por pelo menos 6 meses
            if st.button("Salvar no Histórico"):
                if os.path.exists(HISTORICO_PATH):
                    hist = pd.read_csv(HISTORICO_PATH, dtype={'SKU': str})
                    df_final = pd.concat([hist, dados]).drop_duplicates(subset=['SKU', 'Preço_Pago'])
                else:
                    df_final = dados
                df_final.to_csv(HISTORICO_PATH, index=False)
                st.balloons()
                st.info("O histórico de compras será mantido permanentemente neste arquivo.")
        else:
            st.error("O sistema não encontrou os itens. Verifique se o PDF é o gerado pelo sistema Depecil.")

with tab2:
    st.header("Cruzamento de Ofertas")
    arquivo_jornal = st.file_uploader("Suba o PDF do Jornal (MATRIZ)", type="pdf")
    if arquivo_jornal and os.path.exists(HISTORICO_PATH):
        df_j = extrair_jornal(arquivo_jornal)
        df_h = pd.read_csv(HISTORICO_PATH, dtype={'SKU': str})
        cruzado = pd.merge(df_j, df_h, on="SKU")
        
        # Filtra apenas o que está mais barato que o histórico
        ofertas = cruzado[cruzado['Preço_Oferta'] < cruzado['Preço_Pago']].drop_duplicates(subset=['SKU'])
        
        if not ofertas.empty:
            st.write(f"### 🔥 Encontramos {len(ofertas)} Ofertas!")
            cliente = ofertas['Nome_Cliente'].iloc[0]
            
            # Usa o número real do cliente extraído do PDF
            numero_whats = ofertas['Telefone'].iloc[0]
            tel = st.text_input("Confirmar WhatsApp (Número real):", numero_whats if numero_whats else "55")
            
            msg = f"Olá, *{cliente}*! 👋\n\nFiz uma análise e estes itens que você costuma comprar entraram em promoção:\n\n"
            for _, r in ofertas.iterrows():
                msg += f"✅ *{r['Produto_Jornal']}*\nDe: R${r['Preço_Pago']:.2f} por *R${r['Preço_Oferta']:.2f}*\n\n"
            
            link = f"https://api.whatsapp.com/send?phone={tel}&text={urllib.parse.quote(msg)}"
            st.markdown(f'## [👉 ENVIAR PARA O WHATSAPP REAL]({link})')
        else:
            st.info("Nenhuma oferta do jornal é menor que o preço pago anteriormente.")
