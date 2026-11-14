
"""Leitura de cartões-resposta com alinhamento por quatro quadrados."""

import sys
import cv2
import numpy as np

ALTERNATIVAS = "ABCD"

# Posições de referência dos quatro quadrados
LARGURA_PADRAO = 1024
ALTURA_PADRAO = 1536

PONTOS_DESTINO = np.float32([
    [47, 47],       # Superior esquerdo
    [977, 47],      # Superior direito
    [47, 1447],     # Inferior esquerdo
    [977, 1447],    # Inferior direito
])


def detectar_quadrados(imagem):
    """Localiza os quatro quadrados de referência."""

    cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    altura, largura = cinza.shape

    binaria = cv2.threshold(
        cinza,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )[1]

    contornos, _ = cv2.findContours(
        binaria,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    candidatos = []

    area_minima = altura * largura * 0.00015
    area_maxima = altura * largura * 0.01
    lado_minimo = min(altura, largura) * 0.012
    lado_maximo = min(altura, largura) * 0.08

    for contorno in contornos:
        perimetro = cv2.arcLength(contorno, True)

        if perimetro == 0:
            continue

        aproximacao = cv2.approxPolyDP(
            contorno,
            0.04 * perimetro,
            True
        )

        if len(aproximacao) != 4:
            continue

        if not cv2.isContourConvex(aproximacao):
            continue

        x, y, w, h = cv2.boundingRect(contorno)
        area = cv2.contourArea(contorno)

        if not (lado_minimo <= w <= lado_maximo):
            continue

        if not (lado_minimo <= h <= lado_maximo):
            continue

        if not (area_minima <= area <= area_maxima):
            continue

        proporcao = w / float(h)

        if not 0.65 <= proporcao <= 1.40:
            continue

        centro_x = x + w / 2
        centro_y = y + h / 2

        candidatos.append({
            "x": centro_x,
            "y": centro_y,
            "area": area,
            "caixa": (x, y, w, h)
        })

    # Separa candidatos por região da folha.
    regioes = {
        "superior_esquerdo": [],
        "superior_direito": [],
        "inferior_esquerdo": [],
        "inferior_direito": []
    }

    for c in candidatos:
        x = c["x"]
        y = c["y"]

        if x < largura * 0.18 and y < altura * 0.18:
            regioes["superior_esquerdo"].append(c)

        elif x > largura * 0.82 and y < altura * 0.18:
            regioes["superior_direito"].append(c)

        elif x < largura * 0.18 and y > altura * 0.82:
            regioes["inferior_esquerdo"].append(c)

        elif x > largura * 0.82 and y > altura * 0.82:
            regioes["inferior_direito"].append(c)

    pontos = []

    for nome in (
        "superior_esquerdo",
        "superior_direito",
        "inferior_esquerdo",
        "inferior_direito"
    ):
        opcoes = regioes[nome]

        if not opcoes:
            raise ValueError(
                "Não foi possível localizar o quadrado "
                f"de referência: {nome}. "
                "Verifique se a folha inteira aparece na imagem."
            )

        # Escolhe o maior contorno válido naquela região.
        escolhido = max(opcoes, key=lambda item: item["area"])

        pontos.append([
            escolhido["x"],
            escolhido["y"]
        ])

    return np.float32(pontos)


def alinhar_folha(imagem):
    """Corrige a perspectiva usando os quatro quadrados."""

    pontos_origem = detectar_quadrados(imagem)

    matriz = cv2.getPerspectiveTransform(
        pontos_origem,
        PONTOS_DESTINO
    )

    alinhada = cv2.warpPerspective(
        imagem,
        matriz,
        (LARGURA_PADRAO, ALTURA_PADRAO),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255)
    )

    return alinhada, pontos_origem


def _agrupar_linhas(circulos, tolerancia_y=35):
    """Agrupa os círculos detectados em linhas."""

    ordenados = sorted(circulos, key=lambda item: item[1])
    linhas = []

    for circulo in ordenados:
        if (
            not linhas
            or abs(
                circulo[1] -
                np.mean([p[1] for p in linhas[-1]])
            ) > tolerancia_y
        ):
            linhas.append([circulo])
        else:
            linhas[-1].append(circulo)

    return linhas


def ler_gabarito(caminho_imagem):

    imagem = cv2.imread(caminho_imagem)

    if imagem is None:
        raise ValueError(
            f"Não foi possível abrir a imagem: {caminho_imagem}"
        )

    altura, largura = imagem.shape[:2]

    if altura < 300 or largura < 300:
        raise ValueError("Imagem muito pequena para leitura.")

    # Primeiro corrige a folha pelos quatro quadrados.
    imagem, pontos = alinhar_folha(imagem)

    print("\nQUADRADOS DE REFERÊNCIA DETECTADOS:")

    nomes = [
        "Superior esquerdo",
        "Superior direito",
        "Inferior esquerdo",
        "Inferior direito"
    ]

    for nome, ponto in zip(nomes, pontos):
        print(
            f"{nome}: x={ponto[0]:.1f}, y={ponto[1]:.1f}"
        )

    # Normaliza para a largura utilizada pelo leitor anterior.
    escala = 2064.0 / imagem.shape[1]

    imagem = cv2.resize(
        imagem,
        (2064, int(round(imagem.shape[0] * escala))),
        interpolation=cv2.INTER_CUBIC
    )

    cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    suavizada = cv2.medianBlur(cinza, 5)

    circulos = cv2.HoughCircles(
        suavizada,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=50,
        param1=100,
        param2=28,
        minRadius=13,
        maxRadius=30,
    )

    if circulos is None:
        raise ValueError(
            "Não foi possível localizar as marcações."
        )

    detectados = np.round(circulos[0]).astype(int)

    altura = cinza.shape[0]

    limite_y_superior = int(altura * 0.22)
    limite_y_inferior = int(altura * 0.98)

    detectados = [
        (int(x), int(y), int(r))
        for x, y, r in detectados
        if 600 < x < 1900
        and limite_y_superior < y < limite_y_inferior
    ]

    linhas_detectadas = _agrupar_linhas(detectados)

    linhas = [
        linha
        for linha in linhas_detectadas
        if len(linha) == 4
    ]

    if len(linhas) != 20:
        quantidades = [
            len(linha) for linha in linhas_detectadas
        ]

        raise ValueError(
            "Não foi possível identificar as 20 linhas "
            "com quatro alternativas. "
            f"Foram detectadas {len(linhas)} linhas completas; "
            f"agrupamentos encontrados: {quantidades}."
        )

    respostas = []
    detalhes = []

    for numero, linha in enumerate(linhas, start=1):

        linha = sorted(linha, key=lambda item: item[0])
        intensidades = []

        for x, y, raio in linha:

            margem = max(4, min(7, int(raio * 0.25)))

            roi = cinza[
                y - margem:y + margem + 1,
                x - margem:x + margem + 1
            ]

            if roi.size == 0:
                raise ValueError(
                    f"Falha ao analisar a questão {numero}."
                )

            intensidades.append(float(np.mean(roi)))

        marcadas = [
            indice
            for indice, valor in enumerate(intensidades)
            if valor < 130
        ]

        if len(marcadas) == 0:
            resposta = "EM_BRANCO"

        elif len(marcadas) > 1:
            resposta = "MARCAÇÃO_DUPLA"

        else:
            resposta = ALTERNATIVAS[marcadas[0]]

        respostas.append(resposta)

        detalhes.append({
            "questao": numero,
            "resposta": resposta,
            "intensidades": [
                round(valor, 1)
                for valor in intensidades
            ],
        })

    return respostas, detalhes


if __name__ == "__main__":

    caminho = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "folha_teste2.png"
    )

    try:
        respostas, detalhes = ler_gabarito(caminho)

        print("\nRESULTADO DA LEITURA")

        for item in detalhes:
            print(
                f"Questão {item['questao']:02d}: "
                f"{item['resposta']}"
            )

        print("\nRespostas em sequência:")
        print(", ".join(respostas))

    except Exception as erro:
        print(f"\nERRO: {erro}")
        sys.exit(1)
