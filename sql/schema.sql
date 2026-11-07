-- Esquema estrela — Linha 2 (B3) | PostgreSQL / Supabase
-- Executado pelo ETL (python -m etl.etl_b3 --postgres). Recria as tabelas a cada carga.

DROP TABLE IF EXISTS fato_cotacao;
DROP TABLE IF EXISTS dim_data;
DROP TABLE IF EXISTS dim_ativo;

CREATE TABLE dim_ativo (
    id_ativo      INTEGER PRIMARY KEY,
    ticker        VARCHAR(10)  NOT NULL UNIQUE,
    ticker_yahoo  VARCHAR(15)  NOT NULL,
    empresa       VARCHAR(60)  NOT NULL,
    setor         VARCHAR(40)  NOT NULL
);

CREATE TABLE dim_data (
    data        DATE PRIMARY KEY,
    ano         SMALLINT NOT NULL,
    trimestre   SMALLINT NOT NULL,
    mes         SMALLINT NOT NULL,
    dia_semana  SMALLINT NOT NULL
);

CREATE TABLE fato_cotacao (
    id_ativo             INTEGER NOT NULL REFERENCES dim_ativo (id_ativo),
    data                 DATE    NOT NULL REFERENCES dim_data (data),
    abertura             NUMERIC(14, 6),
    maxima               NUMERIC(14, 6),
    minima               NUMERIC(14, 6),
    fechamento           NUMERIC(14, 6),
    fechamento_ajustado  NUMERIC(14, 6) NOT NULL,
    volume               BIGINT,
    volume_financeiro    NUMERIC(20, 2),
    retorno_diario       DOUBLE PRECISION,
    base100              DOUBLE PRECISION,
    drawdown             DOUBLE PRECISION,
    sma_21               DOUBLE PRECISION,
    sma_50               DOUBLE PRECISION,
    sem_negocio          BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (id_ativo, data)
);

CREATE INDEX idx_fato_data ON fato_cotacao (data);
