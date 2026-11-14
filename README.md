AUTO GABARITO WEB — VERSÃO DE TRABALHO REVISADA

O que foi ajustado nesta cópia:
- leitor de cartões com detecção dos círculos por visão computacional;
- interface com três fluxos: cadastro do gabarito, correção automática e transcrição;
- integração da interface com as rotas /salvar, /gabaritos, /corrigir e /transcrever;
- mensagens de estado e regiões de resultado com aria-live;
- arquivo requirements.txt e testes automatizados do leitor.

REQUISITOS
Python 3.10 ou superior (recomendado: 3.11 ou 3.12).

INSTALAÇÃO (Windows)
1. Abra o terminal na pasta do projeto.
2. Crie o ambiente virtual:
   py -m venv venv
3. Ative o ambiente:
   venv\Scripts\activate
4. Instale as dependências:
   pip install -r requirements.txt
5. Inicie a aplicação:
   python app.py
6. Abra no navegador:
   http://127.0.0.1:5000

TESTES
Execute:
   python -m unittest discover -s tests -v

OBSERVAÇÕES IMPORTANTES
- O leitor foi calibrado inicialmente para o modelo de cartão de 20 questões
  incluído nesta pasta. A imagem deve mostrar a folha inteira, na vertical,
  com boa iluminação e sem cortes importantes.
- A transcrição e a nota calculada devem ser conferidas visualmente antes de
  serem utilizadas. O teste automatizado incluído verifica a folha de teste
  fornecida; não representa validação em diferentes escolas, câmeras ou condições.
- Os gabaritos são gravados em gabaritos.json. Nesta cópia de trabalho o arquivo
  começa vazio; cadastre um gabarito completo de 20 questões pela interface.
- O projeto ainda não está configurado para hospedagem em nuvem nem utiliza
  banco de dados relacional. Essas etapas precisam ser decididas e implementadas
  antes de afirmar que esses requisitos foram atendidos.
- O modo debug do Flask é apropriado apenas para desenvolvimento local.

ATUALIZAÇÃO DO LEITOR (08/11/2026)
- Corrigida a filtragem vertical que descartava círculos abaixo da coordenada fixa y=2400.
- A região vertical agora acompanha a altura real da página após a normalização, atendendo fotos e páginas PDF com proporções diferentes.
- Agrupamentos parciais de círculos no cabeçalho não deslocam mais a numeração das 20 questões; somente linhas com quatro alternativas são consideradas.
- Testes automatizados: 3 testes aprovados, incluindo simulação de página mais alta com a última linha abaixo da antiga faixa de leitura.

IMPORTANTE: esta versão foi validada com a folha de teste incluída no projeto e com uma simulação de página mais alta. Antes de registrar notas reais, confira visualmente os cartões e teste o PDF original que apresentou falha.
