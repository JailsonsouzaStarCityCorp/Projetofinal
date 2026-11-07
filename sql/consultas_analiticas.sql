-- Consultas analíticas de apoio (PostgreSQL). Respondem às perguntas de negócio
-- diretamente no banco e servem para conferir os números do app.

-- Q0. Consulta usada pelo Data App (visão desnormalizada)
SELECT f.data, a.ticker, a.empresa, a.setor,
       f.abertura, f.maxima, f.minima, f.fechamento, f.fechamento_ajustado,
       f.volume, f.volume_financeiro, f.sma_21, f.sma_50
FROM fato_cotacao f
JOIN dim_ativo a USING (id_ativo)
ORDER BY a.ticker, f.data;

-- Q1. Rentabilidade acumulada 2021-2023 (Base 100 final) por ativo
WITH extremos AS (
    SELECT id_ativo,
           FIRST_VALUE(fechamento_ajustado) OVER w AS preco_ini,
           LAST_VALUE(fechamento_ajustado)  OVER w AS preco_fim
    FROM fato_cotacao
    WINDOW w AS (PARTITION BY id_ativo ORDER BY data
                 ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)
)
SELECT a.ticker, a.setor,
       ROUND((MAX(preco_fim) / MAX(preco_ini) * 100)::numeric, 1)       AS base100_final,
       ROUND(((MAX(preco_fim) / MAX(preco_ini) - 1) * 100)::numeric, 2) AS retorno_acum_pct
FROM extremos e JOIN dim_ativo a USING (id_ativo)
GROUP BY a.ticker, a.setor
ORDER BY retorno_acum_pct DESC;

-- Q2. Volatilidade anualizada (% a.a.) e assimetria dos retornos diários
SELECT a.ticker,
       ROUND((STDDEV_SAMP(f.retorno_diario) * SQRT(252) * 100)::numeric, 2) AS vol_anual_pct,
       ROUND((AVG(f.retorno_diario) * 100)::numeric, 4)                     AS ret_medio_diario_pct,
       ROUND((PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY f.retorno_diario) * 100)::numeric, 2) AS var95_pct
FROM fato_cotacao f JOIN dim_ativo a USING (id_ativo)
WHERE f.retorno_diario IS NOT NULL
GROUP BY a.ticker
ORDER BY vol_anual_pct;

-- Q3. Drawdown máximo e data do fundo
SELECT DISTINCT ON (a.ticker)
       a.ticker, ROUND((f.drawdown * 100)::numeric, 2) AS drawdown_max_pct, f.data AS data_fundo
FROM fato_cotacao f JOIN dim_ativo a USING (id_ativo)
ORDER BY a.ticker, f.drawdown ASC;

-- Q4. Retorno por setor e ano (média simples dos ativos)
WITH anual AS (
    SELECT f.id_ativo, d.ano,
           EXP(SUM(LN(1 + COALESCE(f.retorno_diario, 0)))) - 1 AS ret_ano
    FROM fato_cotacao f JOIN dim_data d USING (data)
    GROUP BY f.id_ativo, d.ano
)
SELECT a.setor, an.ano, ROUND((AVG(an.ret_ano) * 100)::numeric, 2) AS ret_medio_pct
FROM anual an JOIN dim_ativo a USING (id_ativo)
GROUP BY a.setor, an.ano
ORDER BY a.setor, an.ano;

-- Q5. Volume financeiro médio diário (R$ milhões) por ativo
SELECT a.ticker, ROUND((AVG(f.volume_financeiro) / 1e6)::numeric, 1) AS vol_fin_medio_mi
FROM fato_cotacao f JOIN dim_ativo a USING (id_ativo)
GROUP BY a.ticker
ORDER BY vol_fin_medio_mi DESC;
