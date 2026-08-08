# Calculador de Rotas

Aplicação web para calcular distâncias rodoviárias em planilhas Excel usando o servidor público do OSRM. O usuário envia um arquivo `.xlsx`, acompanha o processamento e baixa a planilha original enriquecida com distância, status e link para o Google Maps.

## Visão geral

O projeto transforma um processo local em uma aplicação web pronta para uso, sem exigir que o usuário instale Python. O processamento ocorre em memória e preserva, sempre que possível, as abas, os dados e a formatação do arquivo original.

### Principais recursos

- Upload de arquivos `.xlsx` com qualquer nome, limitado a 25 MB.
- Validação amigável de arquivo, cabeçalhos e coordenadas.
- Cálculo de rotas por HTTPS com timeout e tentativas automáticas.
- Processamento paralelo controlado com `ThreadPoolExecutor`.
- Barra de progresso real e métricas de sucesso e falha.
- Preservação da ordem original das linhas.
- Geração de links clicáveis para o Google Maps.
- Interface escura, responsiva e preparada para o Streamlit Community Cloud.
- Processamento isolado em memória, sem armazenamento permanente das planilhas.

## Tecnologias

- Python 3.11+
- Streamlit
- pandas
- openpyxl
- requests
- OSRM

## Estrutura do projeto

```text
.
├── .streamlit/
│   └── config.toml
├── tests/
│   └── test_route_processor.py
├── app.py
├── route_processor.py
├── requirements.txt
├── .gitignore
└── README.md
```

`app.py` contém a interface Streamlit. `route_processor.py` concentra a validação da planilha, as consultas ao OSRM e a geração do arquivo final.

## Instalação local

Clone o repositório e entre na pasta do projeto:

```bash
git clone URL_DO_REPOSITORIO
cd calculador-de-rotas
```

Crie e ative um ambiente virtual:

```bash
python -m venv .venv
```

No Windows:

```powershell
.venv\Scripts\Activate.ps1
```

No Linux ou macOS:

```bash
source .venv/bin/activate
```

Instale as dependências e execute a aplicação:

```bash
pip install -r requirements.txt
streamlit run app.py
```

A aplicação ficará disponível normalmente em `http://localhost:8501`.

## Como usar

1. Prepare uma planilha Excel com os cabeçalhos obrigatórios na primeira linha da aba ativa.
2. Envie o arquivo pela área de upload.
3. Clique em **Calcular rotas**.
4. Acompanhe o progresso e confira o resumo do processamento.
5. Clique em **Baixar planilha calculada**.

Um arquivo chamado `rotas_junho.xlsx`, por exemplo, produzirá `rotas_junho_com_distancia_gps.xlsx`.

## Formato da planilha

A primeira linha da aba ativa deve conter:

| Coluna | Obrigatória | Descrição |
| --- | --- | --- |
| `COORDENADA GPS INICIAL` | Sim | Origem no formato `latitude, longitude` |
| `COORDENADA GPS FINAL` | Sim | Destino no formato `latitude, longitude` |

Exemplo de coordenada válida: `-23.5505, -46.6333`.

Por compatibilidade, o cabeçalho legado `COORDENADA GPG INICIAL` também é aceito. A validação ignora diferenças entre maiúsculas e minúsculas, acentos e espaços extras.

O arquivo processado adiciona ou atualiza:

- `DISTÂNCIA GPS`: distância rodoviária em quilômetros, com duas casas decimais.
- `STATUS DA ROTA`: resultado individual do processamento da linha.
- `LINK DA ROTA`: hiperlink `ABRIR ROTA` para o Google Maps quando a rota é válida.

Uma coordenada inválida afeta apenas a própria linha; as demais continuam sendo processadas.

## Testes

Execute a suíte automatizada com:

```bash
pytest -q
```

Os testes cobrem validação de coordenadas, compatibilidade de cabeçalhos, preservação de abas, criação de hiperlinks, nome do arquivo final e tratamento de arquivos inválidos.

## Publicação no Streamlit Community Cloud

1. Publique o projeto em um repositório no GitHub.
2. Acesse [share.streamlit.io](https://share.streamlit.io/).
3. Entre com a conta vinculada ao GitHub.
4. Clique em **Create app** e escolha o repositório.
5. Informe a branch `main` e o arquivo principal `app.py`.
6. Confirme a publicação.

O projeto não utiliza chaves, senhas ou variáveis secretas.

## Limitações do OSRM público

O endpoint `router.project-osrm.org` é um serviço público de demonstração. Ele pode ficar temporariamente indisponível, responder lentamente ou aplicar restrições de uso. A aplicação reduz esses riscos com paralelismo limitado, timeout e espera progressiva entre novas tentativas.

Para grandes volumes, disponibilidade garantida ou uso comercial crítico, utilize uma instância própria do OSRM ou um provedor de rotas com acordo de nível de serviço.

## Privacidade e segurança

- As planilhas são processadas em memória e não são salvas permanentemente pela aplicação.
- As coordenadas são enviadas ao servidor público do OSRM para o cálculo das rotas.
- Os links gerados direcionam o usuário ao Google Maps.
- Não envie dados pessoais, sigilosos ou sensíveis sem avaliar as políticas do OSRM, do Google Maps e da plataforma de hospedagem.
- Nenhuma credencial deve ser adicionada ao código ou versionada no repositório.

## Licença

Este projeto não possui uma licença de código aberto definida. Consulte o responsável antes de reutilizar ou redistribuir o código.
