# Quadro Kanban: cartões sugeridos para o Trello

Crie um quadro **público** com as listas **Backlog · A Fazer · Em Andamento · Concluído** e os
cartões abaixo. Mova cada um conforme o trabalho avança: o histórico de movimentação é a evidência
de gestão ágil. Cole o link do quadro no README.

| # | Cartão | Checklist | Etiqueta |
|---|---|---|---|
| 1 | Definir linha temática e perguntas de negócio | Ler enunciado · escolher Linha 2 · listar as 5 perguntas | Planejamento |
| 2 | Criar repositório e GitFlow | Repo no GitHub · branches `main` e `develop` · `.gitignore` · README inicial | Git |
| 3 | Configurar ambiente | venv · requirements.txt · teste do yfinance | Setup |
| 4 | ETL: extração | Script de download · salvar bruto em `data/raw` · tratar EMBR3/EMBJ3 | Dados |
| 5 | ETL: limpeza | Datas · tipos numéricos · nulos · duplicados · inconsistências OHLC | Dados |
| 6 | ETL: transformação e modelagem | Retorno, Base 100, drawdown, SMA · esquema estrela · CSVs | Dados |
| 7 | Banco na nuvem (Supabase) | Criar projeto · `schema.sql` · carga com `--postgres` · testar consulta | Dados |
| 8 | Dicionário de dados | Campos, tipos, significado, regras de cálculo | Documentação |
| 9 | App: conexão e cache | `st.connection` · fallback CSV · `@st.cache_data(ttl)` | Streamlit |
| 10 | App: filtros e estado | Setor → ativos · período · `session_state` · botão resetar | Streamlit |
| 11 | App: KPIs | 5 `st.metric` com delta | Streamlit |
| 12 | App: visualizações | Base 100 · risco x retorno · histograma · drawdown · SMA · correlação | Visualização |
| 13 | App: storytelling e UX | Contexto → insight → ação · formato BR · revisão Nielsen | UX |
| 14 | App: exportação e metodologia | `download_button` · aba de metodologia e limitações | Streamlit |
| 15 | Testes | pytest das fórmulas · conferir números com `consultas_analiticas.sql` | Qualidade |
| 16 | Deploy no Streamlit Cloud | Secrets · requirements · validar link público | Deploy |
| 17 | README final | Links · achados · referências · prints | Documentação |
| 18 | Vídeo pitch | Roteiro · gravação de 3 a 5 min · upload não listado | Apresentação |
| 19 | Entrega no AVA | 3 links submetidos · não alterar o repositório depois | Entrega |
