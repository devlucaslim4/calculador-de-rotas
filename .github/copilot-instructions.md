# Instruções para agentes do GitHub Copilot

## Objetivo do repositório

Este projeto é uma aplicação Python/Streamlit que importa checklists concluídos do Checklist Fácil ou recebe um arquivo Excel, padroniza os registros, calcula rotas rodoviárias com OSRM e gera uma planilha tratada com distâncias, hodômetros, percentual de diferença e links clicáveis.

## Regras obrigatórias para alterações

1. Preserve as fórmulas, regras de negócio, integrações e o formato de exportação, salvo solicitação explícita em contrário.
2. Não inclua dados fictícios em indicadores, tabelas, mapas ou relatórios.
3. Nunca versione `.streamlit/secrets.toml`, chaves de API, tokens ou dados pessoais.
4. Antes de editar, leia os testes relacionados e identifique o módulo proprietário da regra.
5. Mantenha identidade visual e componentes apresentacionais em `ui_theme.py` sempre que possível.
6. Prefira componentes nativos do Streamlit; use CSS apenas como complemento.
7. Mantenha a interface em português do Brasil e preserve acessibilidade, contraste e responsividade.
8. Execute toda a suíte de testes antes de considerar uma tarefa concluída.

## Arquitetura

| Arquivo | Responsabilidade |
| --- | --- |
| `app.py` | Fluxo principal, estado da sessão e composição da interface. |
| `ui_theme.py` | Design system, CSS e componentes exclusivamente visuais. |
| `checklist_api.py` | Autenticação, paginação e consultas ao Checklist Fácil. |
| `checklist_transform.py` | Mapeamento dos dados da API para o contrato da planilha ERP. |
| `route_processor.py` | Validação do Excel, OSRM, distância GPS, hodômetro, percentual e links. |
| `analysis_engine.py` | Normalização analítica, filtros, métricas, auditoria e relatório Excel. |
| `dashboard.py` | Componentes de mapa, gráficos, filtros e tabelas. |
| `report_export.py` | Relatório PDF. |
| `tests/` | Contratos automatizados das regras existentes. |

## Contratos de negócio importantes

- O período da importação considera a data de conclusão no fuso `America/Sao_Paulo`.
- O início do mês é inclusivo e o início do mês seguinte é exclusivo.
- Apenas checklists concluídos da categoria configurada devem ser importados.
- Registros são deduplicados por ID da resposta.
- Uma coordenada inválida afeta somente a linha correspondente.
- `DISTÂNCIA HODÔMETRO = VALOR ODOMETRO FINAL - VALOR ODOMETRO INICIAL`.
- O valor armazenado em `PERCENTUAL DIFERENÇA %` é `abs(distância_hodômetro - distância_gps) / distância_gps`, formatado como percentual no Excel.
- O percentual somente existe quando a distância GPS é maior que zero.
- O arquivo original deve manter abas, ordem de linhas e dados sempre que tecnicamente possível.
- O botão de importação é o único evento que deve iniciar chamadas à API.

## Identidade visual

- Fundo principal: `#101C2B`.
- Superfícies e cards: `#1D2D40`.
- Destaque e ação principal: `#56CFAD`.
- Textos principais: `#F4F7FA`.
- Textos secundários: `#A7B7C8`.
- Evite gradientes chamativos, emojis, excesso de cores ou elementos sem função.
- Estados de alerta podem usar cores semânticas discretas.
- Não coloque CSS de negócio em `app.py`; amplie `ui_theme.py`.

## Configuração local

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml
streamlit run app.py
```

Preencha `.streamlit/secrets.toml` localmente. Nunca reproduza o conteúdo do token em logs, testes, respostas ou commits.

## Validação obrigatória

```powershell
python -m compileall -q app.py dashboard.py ui_theme.py
python -m pytest -q
```

Quando houver alterações visuais, também valide:

- carregamento inicial sem exceções;
- fluxo de API e de upload;
- estados sem dados e com erros;
- largura de computador e largura reduzida;
- legibilidade das tabelas, métricas, gráficos e mapa;
- ausência de valores inventados.

## Documentação de apoio

- `README.md`: visão geral, instalação e publicação.
- `docs/manual-de-uso.md`: manual operacional do usuário.
- `docs/checklist-facil.md`: detalhes da integração e do mapeamento da API.

Ao finalizar uma alteração, informe claramente os arquivos modificados, os testes executados e qualquer limitação ou hipótese restante.
