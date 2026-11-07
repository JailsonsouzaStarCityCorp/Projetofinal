# GitFlow: passo a passo com commits semânticos

Faça os commits **você mesmo, ao longo do trabalho**. O histórico do repositório é parte da avaliação,
e a data do último commit conta como data de entrega.

```bash
git init
git add README.md .gitignore requirements.txt
git commit -m "chore: estrutura inicial do projeto"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/SEU-REPO.git
git push -u origin main

git checkout -b develop
git push -u origin develop
```

## Uma feature por etapa

```bash
git checkout develop
git checkout -b feature/etl-extracao
git add src/config.py etl/etl_b3.py
git commit -m "feat(etl): extração de cotações B3 via yfinance"
git push -u origin feature/etl-extracao
# Abra um Pull Request feature/etl-extracao -> develop no GitHub e faça o merge
```

Sequência sugerida de branches e mensagens:

| Branch | Commits de exemplo |
|---|---|
| `feature/etl-extracao` | `feat(etl): extração de cotações B3 via yfinance` |
| `feature/etl-limpeza` | `feat(etl): tratamento de nulos, duplicados e datas` |
| `feature/modelagem` | `feat(sql): esquema estrela e carga no PostgreSQL` · `docs: dicionário de dados` |
| `feature/app-base` | `feat(app): conexão resiliente com fallback CSV e cache` |
| `feature/app-filtros` | `feat(app): filtros cruzados com session_state e reset` |
| `feature/app-graficos` | `feat(app): gráficos de Base 100, risco x retorno e drawdown` · `feat(app): médias móveis e correlação` |
| `feature/app-ux` | `style(app): storytelling contexto-insight-ação e formato BR` |
| `feature/testes` | `test: fórmulas de retorno, volatilidade e drawdown` |
| `feature/docs` | `docs: README completo com links e achados` |

Prefixos: `feat` (funcionalidade) · `fix` (correção) · `docs` · `style` · `refactor` · `test` · `chore`.

## Release para produção

```bash
git checkout main
git merge --no-ff develop -m "release: v1.0.0 — entrega final"
git tag v1.0.0
git push origin main --tags
```

O Streamlit Cloud publica a partir da `main`.
