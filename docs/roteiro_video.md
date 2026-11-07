# Roteiro do vídeo pitch (≈ 4 minutos)

Grave a tela com o app aberto no **link público** do Streamlit Cloud. Fale com as suas palavras e use
os números reais que aparecerem nos insights.

| Tempo | Tela | O que dizer |
|---|---|---|
| 0:00–0:25 | Título do app | Apresentação. Linha 2: performance de 12 ações da B3 de 2021 a 2023. Pergunta central: quanto rendeu e qual risco foi assumido |
| 0:25–1:05 | GitHub (estrutura) + `etl_b3.py` | Pipeline: yfinance → limpeza (datas, nulos, duplicados, OHLC) → esquema estrela → Supabase e CSV de contingência. Caminhos relativos e secrets fora do Git |
| 1:05–1:30 | Barra lateral + KPIs | Filtro setor → ativos, atalhos de período, reset, fonte de dados ativa. Leitura dos 5 KPIs |
| 1:30–2:05 | Aba Rentabilidade | Base 100: melhor e pior ativo e o que valeriam R$ 100 |
| 2:05–2:35 | Aba Risco x Retorno | Quadrantes e melhor Sharpe. Mostrar que o ranking muda ao clicar em 2022 |
| 2:35–3:00 | Retornos diários + Drawdown | Caudas pesadas (curtose); ativo mais resiliente; "queda de X% exige alta de Y%" |
| 3:00–3:25 | Médias móveis + Correlação | SMA 21/50 e cruzamentos; pares mais e menos correlacionados para diversificação |
| 3:25–3:45 | Aba Dados | Exportação do CSV filtrado |
| 3:45–4:15 | Aba Metodologia | Limitações: análise histórica, correlação não é causalidade, não é recomendação. Encerramento e agradecimento |

Dicas: resolução 1080p, zoom do navegador em 90%, filtros resetados antes de começar.
Publique no YouTube como **não listado**.
