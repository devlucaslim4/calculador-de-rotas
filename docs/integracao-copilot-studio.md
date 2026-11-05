# Manual de integração — Microsoft Copilot Studio e Teams

Este documento orienta a publicação da API REST do **Calculador de Rotas**, sua conexão ao Microsoft Copilot Studio e a entrega da planilha Excel no Microsoft Teams.

## 1. Situação da integração

| Item | Situação |
| --- | --- |
| API FastAPI e contratos Pydantic | Implementado |
| Autenticação por `X-API-Key` | Implementado e testado |
| Importação do Checklist Fácil | Reutiliza o cliente existente |
| Cálculo de rotas, hodômetro e percentual | Reutiliza o motor existente |
| Excel com o mesmo contrato do Streamlit | Implementado e comparado em teste automatizado |
| Link HTTPS assinado e com expiração | Implementado e testado localmente |
| Contrato Swagger/OpenAPI 2.0 | Implementado em `openapi-copilot.json` |
| Aplicação Streamlit existente | Preservada |
| Hospedagem pública da FastAPI | Depende da criação do serviço pelo administrador |
| Conexão no Copilot Studio | Depende da conta e do ambiente Microsoft do administrador |
| Publicação do agente no Teams | Depende das permissões e políticas do tenant Microsoft |

Não foi simulada uma conexão Microsoft concluída. O código está pronto; hospedagem, credenciais, conexão e publicação do agente são etapas administrativas externas.

## 2. O que foi reutilizado

A API não contém uma segunda versão das regras de negócio.

```text
Copilot Studio / Teams
          |
          | HTTPS + X-API-Key
          v
      FastAPI (api/)
          |
          v
CalculadorService (services/calculador.py)
          |
          +-- checklist_api.py          consulta e paginação
          +-- checklist_transform.py    padrão ERP
          +-- route_processor.py        OSRM, hodômetro, percentual e Excel
          +-- analysis_engine.py        filtros, métricas e auditoria
```

O Streamlit continua chamando os mesmos módulos. A nova classe `CalculadorService` apenas coordena essas funções para uso sem interface gráfica.

## 3. Endpoints disponíveis

| Método e rota | Autenticação | Finalidade |
| --- | --- | --- |
| `GET /api/health` | Pública | Confirma se o serviço está ativo e configurado. |
| `GET /api/opcoes` | `X-API-Key` | Lista meses, operações e filtros realmente suportados. |
| `POST /api/processar` | `X-API-Key` | Importa o período, calcula as rotas e cria o Excel temporário. |
| `POST /api/gerar-planilha` | `X-API-Key` | Renova o link de uma planilha já processada, sem recalcular. |
| `GET /api/arquivos/{id}` | Token na URL | Entrega o Excel por link assinado e temporário. |

Os filtros de `/api/processar` afetam os indicadores e a prévia JSON. O Excel preserva todos os registros do período, como ocorre no fluxo normal do sistema.

## 4. Configuração segura

Copie `.env.example` apenas como referência. Não versione o arquivo `.env` preenchido.

Variáveis obrigatórias:

| Variável | Uso |
| --- | --- |
| `ROUTES_API_KEY` | Autentica o Copilot Studio na FastAPI. |
| `FILE_SIGNING_SECRET` | Assina os links temporários; deve ser diferente da chave acima. |
| `CHECKLIST_FACIL_API_TOKEN` | Consulta a API Analytics do Checklist Fácil. |
| `PUBLIC_API_BASE_URL` | URL HTTPS pública da FastAPI, sem barra final. |

Também podem ser informados categoria, fuso, validade do link, tamanho máximo e IDs dos itens. Os valores e nomes completos estão em `.env.example`.

Gere dois segredos longos e independentes. No PowerShell, um exemplo que não imprime nem grava credenciais no repositório é:

```powershell
[guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
```

Execute uma vez para `ROUTES_API_KEY` e novamente para `FILE_SIGNING_SECRET`.

## 5. Executar localmente

No diretório do projeto:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Defina as variáveis apenas na sessão atual:

```powershell
$env:ROUTES_API_KEY = "SUA_CHAVE_DO_COPILOT"
$env:FILE_SIGNING_SECRET = "OUTRO_SEGREDO"
$env:CHECKLIST_FACIL_API_TOKEN = "SUA_CHAVE_DO_CHECKLIST"
$env:PUBLIC_API_BASE_URL = "http://localhost:8000"
```

Inicie a API:

```powershell
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
```

Endereços locais:

- documentação Swagger: <http://localhost:8000/docs>;
- contrato OpenAPI 3 gerado pelo FastAPI: <http://localhost:8000/openapi.json>;
- saúde: <http://localhost:8000/api/health>.

O arquivo usado pelo Copilot Studio é o `openapi-copilot.json`, em Swagger 2.0, e não o OpenAPI 3 gerado automaticamente.

## 6. Testar a API local

Verificar as opções:

```powershell
$headers = @{ "X-API-Key" = $env:ROUTES_API_KEY }
Invoke-RestMethod `
  -Uri "http://localhost:8000/api/opcoes" `
  -Headers $headers
```

Processar outubro de 2026:

```powershell
$body = @{
  ano = 2026
  mes = 10
  filtros = @{ usuario = @("Ana") }
  limite_previa = 10
} | ConvertTo-Json -Depth 5

$resultado = Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/api/processar" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body

$resultado
$resultado.arquivo.url_download
```

Exemplo reduzido de requisição JSON:

```json
{
  "ano": 2026,
  "mes": 10,
  "filtros": {
    "usuario": ["Ana"],
    "unidade": [],
    "regiao": [],
    "motivo": [],
    "centro_custo": [],
    "status": [],
    "data_inicio": "2026-10-01",
    "data_fim": "2026-10-31"
  },
  "limite_previa": 10
}
```

Exemplo estrutural de resposta. Números, IDs e URL abaixo ilustram o formato; a API usa somente dados reais no processamento:

```json
{
  "status": "concluido",
  "mensagem": "Processamento concluído: 1 rota(s) calculada(s).",
  "periodo": {"ano": 2026, "mes": 10},
  "contagens": {
    "encontrados": 1,
    "validos_para_rota": 1,
    "inconsistentes": 0,
    "duplicados_consolidados": 0,
    "rotas_calculadas": 1,
    "rotas_nao_calculadas": 0
  },
  "indicadores": {"Total de rotas únicas": 1},
  "previa": [],
  "avisos": [],
  "arquivo": {
    "id": "00000000-0000-0000-0000-000000000000",
    "nome": "checklists_2026_10_tratada.xlsx",
    "url_download": "https://SUA-API/api/arquivos/ID?token=TOKEN_TEMPORARIO",
    "expira_em": "2026-10-26T18:00:00+00:00"
  }
}
```

## 7. Hospedagem sem alterar o Streamlit

### Por que a API precisa de outro serviço

O Streamlit Community Cloud inicia uma aplicação a partir do arquivo de entrada com `streamlit run`. Ele não publica automaticamente um segundo processo ASGI/FastAPI na mesma URL. A documentação de implantação do Streamlit trata um único entrypoint por aplicativo. Portanto:

- mantenha <https://calculador-de-rotas.streamlit.app/> para a interface;
- publique `api.main:app` como um serviço web HTTPS separado;
- ambos usam o mesmo repositório e os mesmos módulos Python.

Referência: [organização de arquivos no Streamlit Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization).

### Alternativa inicial de custo zero: Render

O repositório inclui `render.yaml`. Para criar o serviço:

1. Acesse <https://dashboard.render.com/> e conecte o GitHub.
2. Escolha **New > Blueprint**.
3. Selecione o repositório `calculador-de-rotas`.
4. Confirme o serviço `calculador-de-rotas-api` no plano gratuito.
5. Cadastre como secret:
   - `ROUTES_API_KEY`;
   - `FILE_SIGNING_SECRET`;
   - `CHECKLIST_FACIL_API_TOKEN`;
   - `PUBLIC_API_BASE_URL`, usando a URL final fornecida pelo Render.
6. Aguarde o deploy e abra `https://SUA-API.onrender.com/api/health`.
7. Confirme que `configurado` é `true`.

O comando de inicialização já está no Blueprint:

```text
uvicorn api.main:app --host 0.0.0.0 --port $PORT --no-access-log
```

Limitações práticas do plano gratuito do Render:

- o serviço pode adormecer após período sem tráfego, causando atraso na primeira chamada;
- o sistema de arquivos é efêmero, então um restart invalida planilhas temporárias;
- há cota mensal e limites de recursos;
- o próprio Render não recomenda instâncias gratuitas para produção crítica.

Consulte os valores e condições atuais antes de publicar: [serviços gratuitos do Render](https://render.com/docs/free) e [deploy de FastAPI no Render](https://render.com/docs/deploy-fastapi).

Para uso corporativo com disponibilidade, retenção ou alto volume, será necessário um host persistente e um armazenamento de objetos. Nenhum serviço pago foi contratado por esta implementação.

## 8. Preparar o arquivo OpenAPI para o Copilot Studio

Depois do deploy, abra `openapi-copilot.json` e substitua:

```json
"host": "calculador-de-rotas-api.onrender.com"
```

pelo domínio real, sem `https://` e sem barra final. Mantenha:

```json
"basePath": "/api",
"schemes": ["https"]
```

Valide o JSON:

```powershell
python -m json.tool openapi-copilot.json > $null
```

O Copilot Studio aceita definições OpenAPI v2 para ferramentas REST API; a documentação também recomenda descrições claras de operações e parâmetros para a seleção correta pelo agente. Referência: [adicionar uma ferramenta REST API a um agente](https://learn.microsoft.com/en-us/microsoft-copilot-studio/agent-extend-action-rest-api).

## 9. Conectar ao Microsoft Copilot Studio

Os nomes da interface podem variar conforme a atualização do produto, mas o fluxo administrativo é:

1. Abra o agente no Copilot Studio.
2. Entre em **Tools/Ferramentas** e escolha **Add a tool/Adicionar ferramenta**.
3. Selecione a opção de **REST API** e importe `openapi-copilot.json`.
4. Revise as operações importadas:
   - `verificarSaude`;
   - `listarOpcoes`;
   - `processarPeriodo`;
   - `renovarLinkPlanilha`;
   - `baixarPlanilha`.
5. Configure autenticação por API key:
   - local: cabeçalho;
   - nome: `X-API-Key`;
   - valor: o mesmo de `ROUTES_API_KEY` no host.
6. Armazene a credencial na conexão do ambiente Microsoft; não a coloque nas instruções do agente nem em mensagens.
7. Nas instruções do agente, informe que:
   - mês e ano são obrigatórios para processar;
   - deve perguntar apenas os parâmetros ausentes;
   - deve chamar `processarPeriodo` uma única vez;
   - deve resumir `contagens`, `indicadores` e `avisos` sem inventar valores;
   - deve apresentar `arquivo.url_download` como link clicável quando `arquivo` existir;
   - pode chamar `renovarLinkPlanilha` com `arquivo.id` se o link expirar.
8. Teste com um período pequeno e confira o Excel antes de publicar.

Conectores personalizados também usam OpenAPI 2.0 e suportam autenticação por API key. Referência: [FAQ de conectores personalizados](https://learn.microsoft.com/en-us/connectors/custom-connectors/faq).

### Instrução sugerida para o agente

```text
Você consulta dados do Calculador de Rotas somente pelas ferramentas disponíveis.
Para processar, confirme mês e ano. Não invente métricas, usuários, unidades ou rotas.
Depois de processar, resuma as contagens e os avisos retornados. Quando o campo
arquivo existir, apresente arquivo.url_download como “Baixar planilha tratada”.
Informe que o link é temporário. Se não houver arquivo, explique a mensagem retornada.
Nunca revele chaves, tokens ou detalhes internos de erro.
```

## 10. Exemplos de perguntas ao agente

- “Calcule as rotas concluídas de outubro de 2026.”
- “Quantas rotas válidas tivemos em setembro de 2026?”
- “Processe outubro de 2026 somente para a usuária Ana.”
- “Gere a planilha tratada das rotas de agosto de 2026.”
- “Renove o link da planilha que você acabou de gerar.”

O agente não deve responder perguntas que exijam dados não expostos pelo motor atual nem criar indicadores fictícios.

## 11. Entregar o Excel no Teams

O fluxo implementado usa um link HTTPS assinado:

1. `processarPeriodo` gera o arquivo temporário.
2. A resposta contém `arquivo.url_download` e `arquivo.expira_em`.
3. O agente publica a URL como link clicável na conversa do Teams.
4. O navegador baixa o Excel sem exigir o cabeçalho `X-API-Key`, pois o token assinado já está na URL.
5. O link expira, por padrão, em 15 minutos.

Esse desenho evita retornar caminhos locais e evita expor a chave do Copilot ao navegador. O link deve ser tratado como informação confidencial enquanto estiver válido.

Não foi implementado upload direto do arquivo para SharePoint, OneDrive ou para o anexo nativo da mensagem do Teams. Isso exigiria Microsoft Graph, OAuth/Entra ID e permissões adicionais. Para a primeira versão, o link temporário é o caminho mais simples e compatível.

Depois de testar o agente, use o fluxo de publicação do Copilot Studio para adicioná-lo ao canal do Teams permitido pelo tenant. Referência: [conectar e publicar um agente no Teams](https://learn.microsoft.com/en-us/microsoft-copilot-studio/publication-add-bot-to-microsoft-teams).

## 12. Segurança e operação

- Use segredos diferentes para API e arquivos.
- Rotacione `ROUTES_API_KEY` e atualize a conexão no Copilot Studio quando necessário.
- Nunca inclua tokens em Git, logs, prompts ou respostas.
- Mantenha o access log desativado ou com redação da query string, pois o link de download leva um token temporário na URL.
- A API limita o Excel a 25 MB por padrão.
- IDs de arquivo são UUIDs, nomes são sanitizados e links expiram.
- Arquivos vencidos são removidos durante novas operações.
- Erros externos são convertidos em mensagens controladas; cabeçalhos e credenciais não são retornados.
- A autenticação por API key protege a integração inicial, mas não oferece autorização individual por usuário. Para auditoria por identidade corporativa, evolua para OAuth 2.0 com Microsoft Entra ID.
- O OSRM público continua sujeito a indisponibilidade e limites próprios.

## 13. Testes e manutenção

Execute:

```powershell
pip install -r requirements-dev.txt
python -m pytest -q
```

Os testes da integração cobrem:

- saúde e autenticação;
- validação de parâmetros;
- processamento e resposta JSON;
- assinatura, expiração lógica e renovação de links;
- download sem exposição de caminho local;
- contrato Swagger 2.0;
- equivalência célula a célula, formato e hiperlink entre o Excel do serviço e o pipeline já usado pelo Streamlit.

Antes de atualizar a API, preserve as funções proprietárias das regras em `checklist_api.py`, `checklist_transform.py`, `route_processor.py` e `analysis_engine.py`.
