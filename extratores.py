import re
import pdfplumber
import pandas as pd

# ========= PEDIDOS PDF =========
def extrair_pedido_pdf(file):
    itens = []  # Lista para armazenar os itens do pedido
    cliente = {"codigo": None, "nome": None}  # Dicionário para armazenar as informações do cliente

    # Abrindo o arquivo PDF com pdfplumber
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            texto = page.extract_text()  # Extrai o texto da página
            if not texto:  # Se não houver texto na página, ignora
                continue

            # Extraindo as informações do cliente
            for l in texto.split("\n"):
                if "Cliente" in l and not cliente["nome"]:
                    cliente["nome"] = l.split(":")[-1].strip()
                if "Código" in l and not cliente["codigo"]:
                    cliente["codigo"] = re.sub(r"\D", "", l)  # Retira qualquer caractere não numérico

            # Extraindo a tabela de itens do pedido
            tabela = page.extract_table()  # Extrai a tabela da página
            if not tabela:  # Se não houver tabela, ignora
                continue

            # Processando cada linha da tabela
            for row in tabela[1:]:  # Ignorando o cabeçalho da tabela
                try:
                    # Ajustando a extração dos campos: código, nome, quantidade, preço e total
                    codigo = re.sub(r"\D", "", row[0])  # Retira qualquer caractere não numérico no código
                    nome = row[1].strip()  # Nome do produto
                    qtde = float(row[2].replace(",", "."))  # Quantidade do produto (com conversão de vírgula para ponto)
                    preco = float(row[3].replace(".", "").replace(",", "."))  # Preço unitário
                    total = qtde * preco  # Total do item (quantidade * preço)

                    # Adicionando o item à lista de itens
                    itens.append({"codigo": codigo, "nome": nome, "qtde": qtde, "preco": preco, "total": total})

                except Exception as e:
                    print(f"Erro ao processar linha: {row}, erro: {e}")
    
    return cliente, itens  # Retorna as informações do cliente e os itens do pedido
