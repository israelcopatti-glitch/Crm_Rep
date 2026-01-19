import re
import pdfplumber
import pandas as pd

# ==================================================
# EXTRAÇÃO DE PEDIDOS DE VENDA (PDF DEPECIL)
# ==================================================
def extrair_pedido_pdf(file):
    itens = []
    cliente = {"codigo": None, "nome": None}

    with pdfplumber.open(file) as pdf:
        for p in pdf.pages:
            texto = p.extract_text()
            if not texto:
                continue

            linhas = texto.split("\n")

            for l in linhas:
                if "Cliente" in l and not cliente["nome"]:
                    cliente["nome"] = l.split(":")[-1].strip()

                if "Código" in l and not cliente["codigo"]:
                    cliente["codigo"] = re.sub(r"\D", "", l)

            tabela = p.extract_table()
            if not tabela:
                continue

            for row in tabela[1:]:
                try:
                    codigo = re.sub(r"\D", "", row[0]) if row[0] else None
                    nome = row[1].strip() if row[1] else None
                    qtde = float(row[2].replace(",", ".")) if row[2] else 0
                    preco = float(row[3].replace(".", "").replace(",", ".")) if row[3] else 0
                    total = float(row[4].replace(".", "").replace(",", ".")) if row[4] else 0
                except:
                    continue

                if codigo and nome:
                    itens.append({
                        "codigo": codigo,
                        "nome": nome,
                        "qtde": qtde,
                        "preco": preco,
                        "total": total
                    })

    return cliente, itens


# ==================================================
# EXTRAÇÃO
