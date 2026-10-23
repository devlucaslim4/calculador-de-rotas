# Calculador de Rotas

Aplicação web para importar checklists concluídos diretamente da API Analytics do Checklist Fácil ou receber uma planilha Excel manual, padronizar os dados e calcular distâncias rodoviárias com o servidor público do OSRM.

## Visão geral

O projeto transforma um processo local em uma aplicação web pronta para uso, sem exigir que o usuário instale Python. O processamento ocorre em memória e preserva, sempre que possível, as abas, os dados e a formatação do arquivo original.

### Principais recursos

- Upload de arquivos `.xlsx` com qualquer nome, limitado a 25 MB.
- Importação manual, sob demanda, da categoria `2879584` do Checklist Fácil.
- Mês atual pré-selecionado e consulta de meses anteriores pela data de conclusão.
- Paginação completa, deduplicação por ID e rejeição de respostas parciais da API.
- Geração do Excel padronizado antes do cálculo; somente a ausência de coordenadas válidas impede uma rota.
- Validação amigável de arquivo, cabeçalhos e coordenadas.
- Cálculo de rotas por HTTPS com timeout e tentativas automáticas.
- Consulta agregada das respostas da API, evitando uma requisição por checklist.
- Cálculo matricial de rotas em lotes e reaproveitamento de pares de coordenadas repetidos.
- Preenchimento de hodômetro inicial e final por `ID RESPOSTA`, com cálculo da diferença por checklist.
- Preenchimento do percentual absoluto entre a distância do hodômetro e a distância GPS, usando a distância GPS como base.
- Cache temporário para consultas e cálculos repetidos do mesmo período.
- Processamento paralelo controlado para funções de rota personalizadas.
- Barra de progresso real e métricas de sucesso e falha.
- Preservação da ordem original das linhas.
- Geração de links clicáveis para o Google Maps.
- Interface escura, responsiva e preparada para o Streamlit Community Cloud.
- Processamento isolado em memória, sem armazenamento permanente das planilhas.
- Dashboard agrupado na aba `Análise de dados`, carregado automaticamente após o processamento e sem repetir consultas ao OSRM.
- Filtros por período, usuário, unidade, região, motivo, centro de custo e status, conforme disponibilidade.
- Indicadores por rota única, gráficos interativos e auditoria configurável de inconsistências.
- Downloads dos dados filtrados, inconsistências e relatórios consolidados em PDF e Excel.

## Tecnologias

- Python 3.11+
- Streamlit
- pandas
- openpyxl
- requests
- OSRM
- Plotly

## Estrutura do projeto

```text
.
├── .streamlit/
│   └── config.toml
├── tests/
│   ├── test_analysis_engine.py
│   ├── test_checklist_api.py
│   ├── test_checklist_transform.py
│   └── test_route_processor.py
├── analysis_engine.py
├── app.py
├── checklist_api.py
├── checklist_transform.py
├── dashboard.py
├── docs/
│   └── checklist-facil.md
├── route_processor.py
├── requirements.txt
├── .gitignore
└── README.md
```

`app.py` organiza o fluxo principal e o estado da sessão. `checklist_api.py` consulta a API com paginação, retentativas e validação de completude. `checklist_transform.py` mapeia os dados para o padrão ERP e gera o Excel. `route_processor.py` mantém a validação da planilha, as consultas ao OSRM e a geração do arquivo final. `analysis_engine.py` trata os indicadores, a auditoria e os relatórios.

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

## Configurar a API do Checklist Fácil

Copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml` e preencha a chave emitida pelo Checklist Fácil. Esse arquivo real é ignorado pelo Git.

```toml
[checklist_facil]
api_token = "SUA_CHAVE"
category_id = 2879584
timezone = "America/Sao_Paulo"

[checklist_facil.items]
odometer_start_item_id = 0
odometer_end_item_id = 0
reason_item_id = 0
cost_center_item_id = 0
gps_start_item_id = 0
gps_end_item_id = 0
```

Os quatro primeiros IDs identificam as perguntas de hodômetro inicial, hodômetro final, motivo e centro de custo. O valor `0` ativa a descoberta por nome. Depois da primeira consulta, abra **Itens da categoria e mapeamento utilizado** para conferir os IDs encontrados e, se necessário, fixá-los nos secrets. As coordenadas usam por padrão os campos inicial/final da avaliação; os dois IDs de GPS só são necessários quando o formulário guarda coordenadas em perguntas próprias.

## Como usar a importação direta

1. Abra **Calcular Rotas** e selecione **Importar do Checklist Fácil**.
2. Escolha o mês e o ano. O mês atual já aparece selecionado.
3. Clique em **Importar e calcular rotas**. Nada é consultado automaticamente ao abrir ou atualizar a página.
4. A aplicação padroniza os registros válidos e executa automaticamente o mesmo processamento OSRM usado no upload manual.
5. Confira as quantidades encontradas, válidas e com inconsistências, o mapeamento e a prévia.
6. Clique em **Baixar planilha com rotas calculadas** ou abra **Análise de Dados**.

A consulta continua dependendo de um clique explícito em **Importar e calcular rotas**. Apenas trocar a origem, o mês ou o ano não dispara chamadas à API.

O período considera `DATA CONCLUSÃO` em `America/Sao_Paulo`: o início do mês é inclusivo e o início do mês seguinte é exclusivo. Assim, uma rota iniciada no mês anterior e concluída no mês selecionado pertence ao mês selecionado.

## Como usar o upload manual

1. Selecione **Enviar planilha Excel**.
2. Prepare uma planilha Excel com os cabeçalhos obrigatórios na primeira linha da aba ativa.
3. Envie o arquivo e clique em **Calcular distâncias**.
4. Acompanhe o progresso e confira o resumo do processamento.
5. Clique em **Baixar planilha calculada**.

Depois do processamento, abra a aba **Análise de dados**. O dashboard já estará pronto e usa os dados mantidos na sessão, portanto filtros e gráficos não fazem novas chamadas à API de rotas. O relatório executivo pode ser baixado em PDF e o relatório detalhado em Excel.

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
pip install -r requirements-dev.txt
pytest -q
```

Os testes cobrem paginação, mês atual e histórico, limites de data no fuso local, autenticação, respostas incompletas, categoria incorreta, deduplicação, transformação, layout do Excel e paridade do cálculo entre upload e API. Também verificam validação de coordenadas, preservação de abas, hiperlinks e relatórios.

Também são verificados a deduplicação de rotas por ID, o cálculo de hodômetro, os filtros, a auditoria e a abertura do relatório Excel. O limite conservador para uma distância de hodômetro fora do padrão é de 2.000 km por rota e pode ser alterado em `analysis_engine.py`.

## Publicação no Streamlit Community Cloud

1. Publique o projeto em um repositório no GitHub.
2. Acesse [share.streamlit.io](https://share.streamlit.io/).
3. Entre com a conta vinculada ao GitHub.
4. Clique em **Create app** e escolha o repositório.
5. Informe a branch `main` e o arquivo principal `app.py`.
6. Em **Advanced settings > Secrets**, cole o conteúdo de `.streamlit/secrets.toml.example` com a chave e os IDs reais.
7. Confirme a publicação.

A credencial fica somente no servidor do Streamlit. Não a coloque em arquivos versionados, código, logs ou campos visíveis da interface.

## Limitações do OSRM público

O endpoint `router.project-osrm.org` é um serviço público de demonstração. Ele pode ficar temporariamente indisponível, responder lentamente ou aplicar restrições de uso. A aplicação reduz esses riscos com paralelismo limitado, timeout e espera progressiva entre novas tentativas.

Para grandes volumes, disponibilidade garantida ou uso comercial crítico, utilize uma instância própria do OSRM ou um provedor de rotas com acordo de nível de serviço.

## Privacidade e segurança

- As planilhas são processadas em memória e não são salvas permanentemente pela aplicação.
- A chave da API é lida exclusivamente dos secrets do Streamlit e enviada no cabeçalho `Authorization`.
- A API só é consultada quando o usuário clica no botão; a troca de filtros não dispara chamadas.
- As coordenadas são enviadas ao servidor público do OSRM para o cálculo das rotas.
- Os links gerados direcionam o usuário ao Google Maps.
- Não envie dados pessoais, sigilosos ou sensíveis sem avaliar as políticas do OSRM, do Google Maps e da plataforma de hospedagem.
- Nenhuma credencial deve ser adicionada ao código ou versionada no repositório.

## Documentação da integração

O mapeamento completo de campos, os endpoints utilizados, o tratamento dos limites da API e as pendências para validação com dados reais estão em [`docs/checklist-facil.md`](docs/checklist-facil.md).

## Licença

Este projeto não possui uma licença de código aberto definida. Consulte o responsável antes de reutilizar ou redistribuir o código.
