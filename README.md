# Calculador de Rotas

Aplicação Streamlit que recebe uma planilha Excel, calcula distâncias rodoviárias pelo servidor público do OSRM e devolve o arquivo com distância, status e um link clicável para o Google Maps.

## Executar localmente

Requer Python 3.11 ou superior.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Abra o endereço exibido pelo Streamlit, normalmente `http://localhost:8501`.

## Como usar

1. Envie um arquivo `.xlsx` de até 25 MB.
2. Clique em **Calcular rotas**.
3. Acompanhe o progresso e confira o resumo.
4. Baixe a planilha calculada. O nome original é preservado com o sufixo `_com_distancia_gps`.

Os dados são processados em memória e não são gravados permanentemente pelo aplicativo.

## Estrutura da planilha

A primeira linha da aba ativa deve conter:

- `COORDENADA GPS INICIAL`
- `COORDENADA GPS FINAL`

O cabeçalho legado `COORDENADA GPG INICIAL` também é aceito. Maiúsculas, minúsculas, acentos e espaços extras nos cabeçalhos são ignorados. Cada coordenada deve usar `latitude, longitude`, por exemplo `-23.5505, -46.6333`.

A aplicação adiciona ou atualiza `DISTÂNCIA GPS`, `STATUS DA ROTA` e `LINK DA ROTA`. As demais abas, células e formatações são preservadas sempre que possível.

## Publicar no Streamlit Community Cloud

1. Envie estes arquivos para um repositório no GitHub.
2. Acesse o [Streamlit Community Cloud](https://share.streamlit.io/), conecte o repositório e crie um app.
3. Selecione `app.py` como arquivo principal e publique.

Não são necessárias credenciais nem variáveis secretas.

## Limitações e privacidade

O projeto usa o servidor público de demonstração do OSRM. Ele pode aplicar limites, ficar indisponível ou responder lentamente; por isso o aplicativo limita o paralelismo, define timeout e repete falhas temporárias com espera progressiva. Para alto volume ou uso crítico, hospede uma instância própria do OSRM.

As coordenadas são enviadas ao servidor público do OSRM e os links apontam para o Google Maps. Não envie planilhas com dados pessoais, sigilosos ou sensíveis sem avaliar as políticas desses serviços e da hospedagem. O aplicativo não mantém os arquivos permanentemente, mas a infraestrutura de terceiros pode ter seus próprios registros.
