import re
import pdfplumber
import pandas as pd

# ========= PEDIDOS PDF =========
def extrair_pedido_pdf(file):
    itens = []
    cliente = {"codigo": None, "nome": None}

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            texto = page.extract_text()
            if not texto:
                continue

            for l in texto.split("\n"):
                if "Cliente" in l and not cliente["nome"]:
                    cliente["nome"] = l.split(":")[-1].strip()
                if "Código" in l and not cliente["codigo"]:
                    cliente["codigo"] = re.sub(r"\D", "", l)

            tabela = page.extract_table()
            if not tabela:
                continue

            for row in tabela[1:]:
                try:
                    codigo = re.sub(r"\D", "", row[0])
                    nome = row[1].strip()
                    qtde = float(row[2].replace(",", "."))
                    preco = float(row[3].replace(".", "").replace(",", "."))
                    total = float(row[4].replace(".", "").replace(",", "."))
                except:
                    continue

                itens.append({
                    "codigo": codigo,
                    "nome": nome,
                    "qtde": qtde,
                    "preco": preco,
                    "total": total
                })

    return cliente, itens


# ========= JORNAL PR PDF =========
def extrair_jornal_pdf(file):
    lista = []

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            texto = page.extract_text()
            if not texto:
                continue

            nome_atual = None
            for l in texto.split("\n"):
                l = l.strip()

                if l.isupper() and len(l) > 5:
                    nome_atual = l

                m = re.search(r"^(\d{4,}).*(\d+,\d{2})$", l)
                if m and nome_atual:
                    codigo = m.group(1)
                    preco = float(m.group(2).replace(",", "."))
                    lista.append((codigo, nome_atual, preco))

    return lista
