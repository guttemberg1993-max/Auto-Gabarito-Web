import unittest
import tempfile
from pathlib import Path
import cv2
from leitor_gabarito import ler_gabarito


class TestLeitorGabarito(unittest.TestCase):
    def test_leitura_da_folha_de_teste(self):
        base = Path(__file__).resolve().parents[1]
        respostas, detalhes = ler_gabarito(str(base / "folha_teste.png"))
        esperadas = [
            "A", "B", "EM_BRANCO", "C", "D", "D", "C", "B", "A", "A",
            "B", "C", "D", "D", "C", "B", "A", "A", "B", "C",
        ]
        self.assertEqual(respostas, esperadas)
        self.assertEqual(len(detalhes), 20)
        self.assertEqual([item["questao"] for item in detalhes], list(range(1, 21)))

    def test_leitura_com_conteudo_mais_abaixo_na_pagina(self):
        # Simula uma página PDF mais alta, na qual a última linha ultrapassa
        # a antiga coordenada fixa y=2400.
        base = Path(__file__).resolve().parents[1]
        imagem = cv2.imread(str(base / "folha_teste.png"))
        pagina = cv2.copyMakeBorder(
            imagem, 350, 0, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255)
        )
        with tempfile.NamedTemporaryFile(suffix=".png") as arquivo:
            cv2.imwrite(arquivo.name, pagina)
            respostas, detalhes = ler_gabarito(arquivo.name)
        self.assertEqual(len(respostas), 20)
        self.assertEqual(len(detalhes), 20)

    def test_arquivo_inexistente_retorna_erro_claro(self):
        with self.assertRaisesRegex(ValueError, "Não foi possível abrir"):
            ler_gabarito("arquivo_que_nao_existe.png")


if __name__ == "__main__":
    unittest.main()
