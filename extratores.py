import re
import pdfplumber
import pandas as pd

# ================= PEDIDO =================

def extrair_pedido_pdf(file):
    lista = []

    with pdfplumber.open(file) as pdf:
        for p in pdf.pages:
            t = p.extract_text()
            if not t:
                continue

            linhas = t.split("\n")

            cli = fone = None
            for l in linhas:
                if "Cliente" in l and not cli:
                    cli = l.split(":")[-1].strip()
                if "Telefone" in l and not fone:
                    fone = l.split(":")[-1].strip()

            tabela = p.extract_table()
            if not tabela:
                continue

            for row in tabela[1:]:
                sku = re.sub(r"\D", "", row[0]) if row[0] else None
                produto = row[1].strip() if row[1] else None
                valor = None

                if row[2]:
                    valor = float(row[2].replace(".", "").replace(",", "."))

                if cli and sku and valor:
                    lista.append((cli, fone, sku, produto, valor))

    return lista

# ================= JORNAL PDF (CORRIGIDO) =================

def extrair_jornal_pdf(file):
    lista = []

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:

            # --- FORMATO TABELA ---
            rows = page.extract_table()

            if rows:
                for r in rows[1:]:
                    sku = re.sub(r"\D", "", r[0]) if r[0] else ""
                    produto = r[1][:40].strip() if r[1] else ""
                    preco = None

                    if len(r) >= 3 and r[2]:
                        preco = float(r[2].replace(".", "").replace(",", "."))

                    if sku and preco:
                        lista.append((sku, produto, preco))
                continue

            # --- FORMATO BLOCO PR ---
            texto = page.extract_text()
            if not texto:
                continue

            linhas = [l.strip() for l in texto.split("\n") if l.strip()]
            nome_atual = None
            modo_pr = False

            for linha in linhas:
                if linha.isupper() and len(linha) > 5 and not linha.startswith("R$"):
                    nome_atual = linha
                    modo_pr = False
                    continue

                if linha == "R$ PR":
                    modo_pr = True
                    continue

                if modo_pr:
                    m = re.search(r"^(\d+).*?(\d+,\d+)$", linha)
                    if m and nome_atual:
                        sku = m.group(1)
                        preco = float(m.group(2).replace(".", "").replace(",", "."))
                        lista.append((sku, nome_atual[:40], preco))
                    modo_pr = False

    return lista

# ================= JORNAL EXCEL =================

def extrair_jornal_excel(df: pd.DataFrame):
    lista = []

    for _, row in df.iterrows():
        sku = re.sub(r"\D", "", str(row[0])) if row[0] else None
        produto = str(row[1]).strip() if row[1] else None
        preco = None

        if row[2]:
            preco = float(str(row[2]).replace(".", "").replace(",", "."))

        if sku and preco:
            lista.append((sku, produto, preco))

    return lista
