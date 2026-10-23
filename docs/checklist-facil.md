# Integração com o Checklist Fácil

## Escopo

A importação usa a API Analytics oficial em `https://api-analytics.checklistfacil.com.br`. A categoria alvo é `2879584`, extraída da URL informada. Como categoria e checklist são entidades diferentes, a aplicação primeiro consulta `/v1/categories` e resolve o `checklistId` associado. Nenhum ID de checklist é inferido a partir da URL.

## Endpoints

| Finalidade | Endpoint |
| --- | --- |
| Resolver categoria e checklist | `GET /v1/categories` |
| Localizar itens/perguntas | `GET /v1/items` |
| Listar aplicações concluídas | `GET /v1/evaluations` |
| Obter respostas completas | `GET /v3/evaluations/{evaluationId}/results` |
| Nome e tipo do usuário | `GET /v1/users` e `GET /v1/user-types` |
| Unidade e região | `GET /v1/units`, `GET /v1/units/regions` e `GET /v1/regions` |

As listagens usam `page` e `limit=1000` até `meta.hasMore=false`. Se `data`, `meta` ou `hasMore` faltar, se a página devolvida não corresponder à solicitada, ou se o endpoint de respostas indicar mais páginas sem documentar como buscá-las, a operação é cancelada. Não se gera Excel parcial.

## Regra do período

A consulta envia os filtros:

- `status=6` (concluído);
- `checklistId=<ID resolvido>`;
- `deletedAt=null`;
- `concludedAt[gte]=<início do mês>`;
- `concludedAt[lte]=<início do mês seguinte menos 1 microssegundo>`.

Os limites são calculados em `America/Sao_Paulo`. Como defesa adicional, todas as respostas são convertidas de UTC para esse fuso e revalidadas pelo intervalo inclusivo/exclusivo. Registros são deduplicados por `evaluationId`, mantendo a versão de `updatedAt` mais recente.

## Mapeamento para o ERP

| Coluna no Excel | Origem na API |
| --- | --- |
| `DESCRIÇÃO DO STATUS` | status `6`, exibido como `Concluído` |
| `ID RESPOSTA` | `evaluationId` |
| `NOME` | `userId` → `/v1/users.name` |
| `TIPO DE USUÁRIO` | usuário → `userTypeId` → `/v1/user-types.name` |
| `UNIDADE` | `unitId` → `/v1/units.name` |
| `REGIÃO` | unidade → `/v1/units/regions` → `/v1/regions.hierarchyName` ou `name` |
| `DATA INÍCIO` | `startedAt`, convertido para o fuso local |
| `DATA CONCLUSÃO` | `concludedAt`, convertido para o fuso local |
| Coordenadas inicial/final | `initialLatitude/Longitude` e `finalLatitude/Longitude`; perguntas configuradas têm prioridade quando presentes |
| Hodômetros inicial/final | resposta dos IDs configurados/descobertos; usa `number` ou texto numérico |
| `MOTIVO` | resposta do ID configurado/descoberto; suporta texto e opções selecionadas |
| `CENTRO DE CUSTO` | resposta do ID configurado/descoberto; suporta texto e opções selecionadas |
| `DISTÂNCIA HODÔMETRO` | hodômetro final menos inicial |
| `PERCENTUAL DIFERENÇA %` | diferença absoluta entre hodômetro e GPS, dividida pela distância GPS |
| `VALIDAÇÃO` | `Válida` ou lista legível de campos inconsistentes |
| `DISTÂNCIA GPS`, `STATUS DA ROTA`, `LINK DA ROTA` | preenchidos pelo processamento OSRM já existente |

Somente linhas válidas entram na aba principal `CONTROLE QUILOMETRAGEM` e, portanto, no cálculo de rotas. Linhas rejeitadas ficam na aba `INCONSISTENCIAS`, preservando a evidência sem misturá-la ao processamento.

Depois que o usuário clica em **Importar e calcular rotas**, a aplicação executa a importação, a transformação e o cálculo OSRM em sequência. O único download exibido contém `DISTÂNCIA GPS`, `STATUS DA ROTA` e `LINK DA ROTA`, evitando que a base intermediária sem cálculos seja confundida com o arquivo final.

Uma linha segue para o cálculo sempre que possui coordenadas inicial e final válidas. Hodômetro, motivo, centro de custo e dados cadastrais continuam sendo importados quando disponíveis, mas a ausência deles não bloqueia a distância GPS nem o link da rota.

Para reduzir o tempo, as respostas são consultadas pelo endpoint agregado paginado `/v3/evaluations/results`, em vez de uma chamada por avaliação. As distâncias são calculadas em lotes pelo serviço matricial do OSRM, com reaproveitamento de pares de coordenadas repetidos. Consultas idênticas ficam em cache por um minuto e o mesmo conjunto de rotas por uma hora.

As respostas do endpoint agregado são agrupadas pelo `evaluationId`, que corresponde ao `ID RESPOSTA` da planilha. Dentro de cada grupo, os itens configurados de hodômetro inicial e final alimentam `VALOR ODOMETRO INICIAL` e `VALOR ODOMETRO FINAL`; `DISTÂNCIA HODÔMETRO` recebe a diferença entre os dois valores. Itens cujo nome indica GPS nunca são usados como hodômetro.

## Valores de respostas

A versão v3 dos resultados pode devolver o conteúdo em `number`, `text`, `selectedOptions` ou `records`. A transformação prioriza valor numérico, depois texto, opções e, por fim, nome/referência do registro. Respostas de outras categorias são ignoradas. Quando há repetição do mesmo item, o hodômetro inicial usa a primeira resposta e os demais campos usam a mais recente.

## Limites, erros e segurança

- A API é acionada apenas pelo botão **Importar e calcular rotas**.
- O cliente respeita o limite global documentado por meio de um intervalo mínimo entre chamadas.
- Erros transitórios (`429`, `519` e `5xx`) têm espera progressiva e no máximo três tentativas.
- `Retry-After` é respeitado; sem esse cabeçalho, um `429` aguarda 60 segundos.
- Limite diário esgotado interrompe a consulta e informa o valor de `X-DailyLimit-Reset`.
- `401` e `403` viram mensagens de autenticação/permissão, sem imprimir a chave.
- A URL base é fixa em HTTPS, reduzindo o risco de enviar o token a outro host.
- A validação TLS permanece obrigatória e usa o repositório nativo de certificados do sistema operacional por meio de `truststore`, permitindo certificados-raiz corporativos sem recorrer a `verify=False`.
- A chave vem exclusivamente de `st.secrets` e `.streamlit/secrets.toml` está no `.gitignore`.

## Validação pendente com o ambiente real

O código e os testes não precisam de uma credencial real. Antes de publicar em produção, ainda é necessário:

1. Inserir uma chave Analytics com acesso à categoria `2879584` nos secrets.
2. Executar uma consulta de um mês pequeno e conferir os nomes/IDs exibidos no catálogo.
3. Fixar nos secrets os quatro IDs de hodômetro, motivo e centro de custo caso a descoberta por nome não seja inequívoca.
4. Comparar uma amostra do Excel gerado com o ERP e confirmar se a empresa deseja usar as coordenadas da avaliação ou perguntas específicas do formulário.
5. Confirmar o volume máximo mensal e a cota diária da conta, pois cada avaliação exige uma consulta v3 de respostas.
