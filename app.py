from flask import Flask, render_template, request, jsonify
import json
import os
import tempfile
import cv2
import fitz  # PyMuPDF: converte páginas de PDF em imagens
from leitor_gabarito import ler_gabarito

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024  # 40 MB por envio
ARQUIVO_GABARITOS = os.path.join(os.path.dirname(__file__), "gabaritos.json")
ALTERNATIVAS_VALIDAS = {"A", "B", "C", "D"}
EXTENSOES_IMAGEM = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
MAX_PAGINAS_PDF = 60

def carregar_gabaritos():
    if not os.path.exists(ARQUIVO_GABARITOS):
        return []
    try:
        with open(ARQUIVO_GABARITOS, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        return dados if isinstance(dados, list) else []
    except (json.JSONDecodeError, OSError):
        return []

@app.route("/")
def inicio():
    return render_template("index.html")

@app.route("/salvar", methods=["POST"])
def salvar():
    dados = request.get_json(silent=True) or {}
    nome = str(dados.get("nome", "")).strip()
    respostas = dados.get("respostas")

    if not nome or not isinstance(respostas, list) or not respostas:
        return jsonify({"mensagem": "Informe o nome e as respostas do gabarito."}), 400
    if len(respostas) != 20:
        return jsonify({"mensagem": "O gabarito oficial precisa conter exatamente 20 respostas."}), 400
    if not all(r in ALTERNATIVAS_VALIDAS for r in respostas):
        return jsonify({"mensagem": "Use apenas as alternativas A, B, C ou D."}), 400

    gabaritos = carregar_gabaritos()
    novo = {"nome": nome, "respostas": respostas}
    existente = next((i for i, item in enumerate(gabaritos)
                      if item.get("nome", "").casefold() == nome.casefold()), None)
    if existente is None:
        gabaritos.append(novo)
    else:
        gabaritos[existente] = novo

    try:
        with open(ARQUIVO_GABARITOS, "w", encoding="utf-8") as arquivo:
            json.dump(gabaritos, arquivo, ensure_ascii=False, indent=4)
    except OSError:
        return jsonify({"mensagem": "Não foi possível gravar o arquivo de gabaritos."}), 500

    return jsonify({
        "mensagem": "Gabarito oficial salvo com sucesso!",
        "avaliacao": nome,
        "total_questoes": len(respostas)
    })

@app.route("/gabaritos", methods=["GET"])
def listar_gabaritos():
    return jsonify([
        {"nome": item.get("nome", ""), "total_questoes": len(item.get("respostas", []))}
        for item in carregar_gabaritos()
        if len(item.get("respostas", [])) == 20
    ])

def comparar_respostas(respostas_aluno, respostas_oficiais, pagina=None):
    if len(respostas_oficiais) != len(respostas_aluno):
        raise ValueError(
            f"A folha tem {len(respostas_aluno)} questões, mas o gabarito oficial "
            f"tem {len(respostas_oficiais)}. Esta versão do leitor foi testada com 20 questões."
        )

    resultado = []
    acertos = 0
    em_branco = 0
    duplas = 0

    for numero, (aluno, correta) in enumerate(zip(respostas_aluno, respostas_oficiais), start=1):
        acertou = aluno == correta
        if aluno == "EM_BRANCO":
            em_branco += 1
        elif aluno == "MARCAÇÃO_DUPLA":
            duplas += 1
        if acertou:
            acertos += 1
        resultado.append({
            "questao": numero,
            "resposta_aluno": aluno,
            "gabarito": correta,
            "resultado": "Acerto" if acertou else "Erro"
        })

    return {
        "pagina": pagina,
        "total_questoes": len(respostas_aluno),
        "acertos": acertos,
        "erros": len(respostas_aluno) - acertos,
        "em_branco": em_branco,
        "marcacao_dupla": duplas,
        "nota_0_a_10": round(acertos / len(respostas_aluno) * 10, 2),
        "resultados": resultado
    }

@app.route("/corrigir", methods=["POST"])
def corrigir():
    arquivo = request.files.get("imagem")
    nome_avaliacao = request.form.get("avaliacao", "").strip()

    if arquivo is None or not arquivo.filename:
        return jsonify({"mensagem": "Selecione uma foto ou um PDF com os cartões-resposta."}), 400
    if not nome_avaliacao:
        return jsonify({"mensagem": "Selecione o gabarito oficial da avaliação."}), 400

    gabaritos = carregar_gabaritos()
    oficial = next((item for item in gabaritos
                    if item.get("nome", "").casefold() == nome_avaliacao.casefold()), None)
    if oficial is None:
        return jsonify({"mensagem": "Esse gabarito não foi encontrado. Cadastre e salve primeiro."}), 404

    extensao = os.path.splitext(arquivo.filename)[1].lower()
    if extensao not in EXTENSOES_IMAGEM | {".pdf"}:
        return jsonify({"mensagem": "Envie uma imagem PNG/JPG ou um arquivo PDF."}), 400

    caminho = None
    imagens_temporarias = []
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extensao) as temporario:
            caminho = temporario.name
            arquivo.save(caminho)

        caminhos_para_ler = []
        if extensao == ".pdf":
            try:
                documento = fitz.open(caminho)
            except Exception:
                return jsonify({"mensagem": "Não foi possível abrir o PDF. Verifique se o arquivo está íntegro e não protegido por senha."}), 400

            with documento:
                if documento.page_count > MAX_PAGINAS_PDF:
                    return jsonify({"mensagem": f"O PDF tem {documento.page_count} páginas. O limite atual é {MAX_PAGINAS_PDF} páginas por envio."}), 400
                if documento.page_count == 0:
                    return jsonify({"mensagem": "O PDF não contém páginas."}), 400

                for indice, pagina_pdf in enumerate(documento, start=1):
                    pix = pagina_pdf.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    caminho_png = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
                    pix.save(caminho_png)
                    imagens_temporarias.append(caminho_png)
                    caminhos_para_ler.append((indice, caminho_png))
        else:
            caminhos_para_ler.append((1, caminho))

        resultados_paginas = []
        falhas = []
        for numero_pagina, caminho_imagem in caminhos_para_ler:
            try:
                respostas_aluno, _ = ler_gabarito(caminho_imagem)
                comparacao = comparar_respostas(
                    respostas_aluno, oficial.get("respostas", []), pagina=numero_pagina
                )
                comparacao["mensagem"] = "Leitura concluída; confira visualmente antes de registrar a nota."
                resultados_paginas.append(comparacao)
            except (ValueError, cv2.error) as erro:
                falhas.append({"pagina": numero_pagina, "erro": str(erro)})

        return jsonify({
            "mensagem": "Processamento concluído. Confira cada página antes de registrar as notas.",
            "avaliacao": nome_avaliacao,
            "arquivo": os.path.basename(arquivo.filename),
            "total_paginas": len(caminhos_para_ler),
            "paginas_processadas": len(resultados_paginas),
            "falhas": falhas,
            "resultados_paginas": resultados_paginas
        })
    except Exception:
        app.logger.exception("Erro inesperado ao processar cartões-resposta")
        return jsonify({"mensagem": "Ocorreu um erro inesperado durante a leitura. Consulte o terminal para detalhes."}), 500
    finally:
        if caminho and os.path.exists(caminho):
            os.remove(caminho)
        for item in imagens_temporarias:
            if os.path.exists(item):
                os.remove(item)


@app.route("/transcrever", methods=["POST"])
def transcrever():
    """Lê cartões de um PDF/foto e devolve as respostas detectadas sem gabarito oficial."""
    arquivo = request.files.get("imagem")
    if arquivo is None or not arquivo.filename:
        return jsonify({"mensagem": "Selecione uma foto ou um PDF com os cartões-resposta."}), 400

    extensao = os.path.splitext(arquivo.filename)[1].lower()
    if extensao not in EXTENSOES_IMAGEM | {".pdf"}:
        return jsonify({"mensagem": "Envie uma imagem PNG/JPG ou um arquivo PDF."}), 400

    caminho = None
    imagens_temporarias = []
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extensao) as temporario:
            caminho = temporario.name
            arquivo.save(caminho)

        caminhos_para_ler = []
        if extensao == ".pdf":
            try:
                documento = fitz.open(caminho)
            except Exception:
                return jsonify({"mensagem": "Não foi possível abrir o PDF. Verifique se o arquivo está íntegro e não protegido por senha."}), 400
            with documento:
                if documento.page_count > MAX_PAGINAS_PDF:
                    return jsonify({"mensagem": f"O PDF tem {documento.page_count} páginas. O limite atual é {MAX_PAGINAS_PDF} páginas por envio."}), 400
                if documento.page_count == 0:
                    return jsonify({"mensagem": "O PDF não contém páginas."}), 400
                for indice, pagina_pdf in enumerate(documento, start=1):
                    pix = pagina_pdf.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                    caminho_png = tmp.name
                    tmp.close()
                    pix.save(caminho_png)
                    imagens_temporarias.append(caminho_png)
                    caminhos_para_ler.append((indice, caminho_png))
        else:
            caminhos_para_ler.append((1, caminho))

        paginas = []
        falhas = []
        for numero_pagina, caminho_imagem in caminhos_para_ler:
            try:
                respostas, _detalhes = ler_gabarito(caminho_imagem)
                paginas.append({"pagina": numero_pagina, "total_questoes": len(respostas), "respostas": respostas})
            except (ValueError, cv2.error) as erro:
                falhas.append({"pagina": numero_pagina, "erro": str(erro)})

        return jsonify({
            "mensagem": "Transcrição concluída. Confira visualmente as respostas detectadas.",
            "arquivo": os.path.basename(arquivo.filename),
            "total_paginas": len(caminhos_para_ler),
            "paginas_processadas": len(paginas),
            "falhas": falhas,
            "paginas": paginas
        })
    except Exception:
        app.logger.exception("Erro inesperado ao transcrever cartões-resposta")
        return jsonify({"mensagem": "Ocorreu um erro inesperado durante a leitura. Consulte o terminal para detalhes."}), 500
    finally:
        if caminho and os.path.exists(caminho):
            os.remove(caminho)
        for item in imagens_temporarias:
            if os.path.exists(item):
                os.remove(item)

@app.errorhandler(413)
def arquivo_grande(_erro):
    return jsonify({"mensagem": "O arquivo ultrapassa o limite de 40 MB."}), 413

if __name__ == "__main__":
    app.run(debug=True)
