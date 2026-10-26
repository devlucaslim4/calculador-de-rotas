# Manual de Uso — Calculador de Rotas

Este manual descreve o fluxo operacional do Calculador de Rotas, desde a importação dos dados até a análise e exportação dos resultados.

## 1. Acesso ao sistema

A aplicação publicada está disponível em:

<https://calculador-de-rotas.streamlit.app/>

Ao abrir o sistema, o cabeçalho informa se a API do Checklist Fácil está configurada. A navegação principal possui três áreas:

- **Operação:** importa, valida, calcula e exporta os dados.
- **Mapa de rotas:** permite selecionar e explorar individualmente uma rota processada.
- **Indicadores:** apresenta filtros, métricas, gráficos, auditoria e relatórios.

## 2. Fluxo pela API do Checklist Fácil

1. Abra a aba **Operação**.
2. Em **Escolha a origem dos dados**, selecione **Importar do Checklist Fácil**.
3. Selecione o mês e o ano de conclusão.
4. Confira a categoria e o fuso horário exibidos abaixo dos campos.
5. Clique em **Importar, calcular e gerar Excel**.
6. Aguarde o término da consulta e do cálculo. Não feche a página durante o processamento.
7. Confira as quantidades encontradas, as rotas com coordenadas válidas e os registros inconsistentes.
8. Use a busca e o filtro de status para revisar a prévia.
9. Em **Resultados e exportação**, clique em **Baixar planilha com rotas calculadas**.

A troca de mês ou ano não dispara uma consulta automaticamente. A API só é chamada quando o botão de importação é pressionado.

## 3. Fluxo por planilha Excel

1. Abra a aba **Operação**.
2. Selecione **Enviar planilha Excel**.
3. Clique em **Escolher arquivo** e selecione um arquivo `.xlsx` de até 25 MB.
4. Confirme que a primeira linha da aba ativa possui:
   - `COORDENADA GPS INICIAL`
   - `COORDENADA GPS FINAL`
5. Clique em **Calcular rotas e gerar Excel**.
6. Aguarde a validação e o cálculo.
7. Confira os indicadores e baixe o resultado.

O cabeçalho legado `COORDENADA GPG INICIAL` também é aceito para compatibilidade.

## 4. Como interpretar o resultado

| Campo | Significado |
| --- | --- |
| `DISTÂNCIA GPS` | Distância rodoviária calculada pelo OSRM, em quilômetros. |
| `STATUS DA ROTA` | Informa se a linha foi calculada ou qual inconsistência impediu o cálculo. |
| `LINK DA ROTA` | Link clicável para abrir o trajeto no Google Maps. |
| `VALOR ODOMETRO INICIAL` | Hodômetro informado no início do checklist. |
| `VALOR ODOMETRO FINAL` | Hodômetro informado no final do checklist. |
| `DISTÂNCIA HODÔMETRO` | Hodômetro final menos hodômetro inicial. |
| `PERCENTUAL DIFERENÇA %` | Diferença absoluta entre hodômetro e GPS, usando a distância GPS como base. |

O percentual é calculado apenas quando existem valores de hodômetro e uma distância GPS maior que zero.

## 5. Mapa de rotas

O mapa fica disponível depois que uma planilha é processada.

1. Abra **Mapa de rotas**.
2. Use **Filtrar por usuário** quando quiser restringir a lista.
3. Escolha uma rota.
4. Confira usuário, distância GPS, distância do hodômetro e diferença.
5. Clique em **Carregar experiência da rota**.
6. Escolha entre:
   - **Viagem animada:** inicia, pausa ou reinicia o deslocamento do veículo.
   - **Explorar em 3D:** permite mover, ampliar, inclinar e girar o mapa.

O traçado detalhado é carregado somente para a rota selecionada, reduzindo o tempo inicial de processamento.

## 6. Indicadores e auditoria

Na aba **Indicadores**:

1. Selecione o período e os filtros disponíveis.
2. Confira os indicadores de rotas e quilometragem.
3. Navegue entre **Visão geral**, **Dados detalhados** e **Auditoria**.
4. Use **Limpar filtros** para retornar à visão completa.
5. Baixe, conforme necessário:
   - dados filtrados em CSV;
   - relatório executivo em PDF;
   - relatório detalhado em Excel;
   - inconsistências em CSV.

Os indicadores sempre utilizam os dados reais da planilha processada e respeitam os filtros ativos.

## 7. Mensagens e soluções comuns

### API não configurada

O administrador deve cadastrar o conteúdo de `.streamlit/secrets.toml.example` nos Secrets do Streamlit Cloud. A chave real nunca deve ser adicionada ao Git.

### HTTP 401 ou 403

Verifique se a chave da API está válida e se possui acesso à categoria configurada.

### HTTP 422

Confirme categoria, período e IDs dos itens. Consulte **Configuração avançada: itens e mapeamento utilizado** para conferir o catálogo retornado.

### Nenhuma rota válida

Confirme se as coordenadas inicial e final existem e usam o formato `latitude, longitude`, por exemplo `-23.5505, -46.6333`.

### Algumas rotas não foram calculadas

Consulte `STATUS DA ROTA`. O OSRM público pode ficar temporariamente indisponível ou não encontrar um trajeto rodoviário entre os pontos informados.

### Hodômetro não preenchido

Confira se os IDs das perguntas de hodômetro inicial e final estão corretos nos Secrets. O sistema também tenta descobrir os campos pelo nome quando o ID está definido como `0`.

## 8. Privacidade e segurança

- Os arquivos são processados em memória e não ficam armazenados permanentemente pela aplicação.
- A chave da API deve existir somente nos Secrets do Streamlit ou no arquivo local ignorado pelo Git.
- As coordenadas são enviadas ao servidor OSRM para o cálculo rodoviário.
- Os links de rota direcionam ao Google Maps.
- Não publique planilhas que contenham informações pessoais ou sigilosas sem a devida autorização.

## 9. Execução local

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

A aplicação ficará disponível normalmente em `http://localhost:8501`.

Para executar os testes:

```powershell
pip install -r requirements-dev.txt
python -m pytest -q
```

