from fpdf import FPDF

def gerar_pdf(texto, nome_arquivo="documento.pdf"):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    linhas = texto.split("\n")
    for linha in linhas:
        pdf.multi_cell(0, 10, linha)

    pdf.output(nome_arquivo)
    print(f"PDF criado com sucesso: {nome_arquivo}")


if __name__ == "__main__":
    texto_exemplo = """Bem-vindo ao gerador de PDF!
Este PDF foi criado automaticamente.
Você pode editar o conteúdo e gerar outro."""

    gerar_pdf(texto_exemplo, "meu_primeiro_pdf.pdf")
