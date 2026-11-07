"""Pipeline ETL — Linha 2: Performance de Mercado de Ações (B3)

Etapas:
  1. EXTRAÇÃO   -> cotações diárias via API pública do Yahoo Finance (yfinance, sufixo .SA)
                   e gravação do dado bruto em data/raw/ (auditabilidade)
  2. LIMPEZA    -> tipos, datas, duplicados, nulos, inconsistências OHLC, encoding
  3. TRANSFORM. -> retorno diário, volume financeiro, Base 100, drawdown, SMA 21/50
  4. MODELAGEM  -> esquema estrela: dim_ativo, dim_data e fato_cotacao
  5. CARGA      -> CSVs em data/processed/ (contingência do app) e, opcionalmente,
                   PostgreSQL na nuvem (Supabase)

Uso (a partir da raiz do repositório):
    python -m etl.etl_b3                 # baixa da API e gera os CSVs
    python -m etl.etl_b3 --offline       # reprocessa só a partir de data/raw/
    python -m etl.etl_b3 --postgres      # também carrega no PostgreSQL

Respeito aos termos de uso: uma requisição por ativo, com pausa entre elas.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import pandas as pd

# Permite rodar como "python etl/etl_b3.py" também
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import (ATIVOS, CSV_DIM_ATIVO, CSV_FATO, CSV_RESUMO, DATA_FIM,
                        DATA_INICIO, DIR_PROCESSED, DIR_RAW, RAIZ)
from src.metrics import calcular_medias_moveis, recalcular_janela, resumo_por_ativo

RELATORIO: list[str] = []


def log(msg: str) -> None:
    print(msg)
    RELATORIO.append(msg)


# --------------------------------------------------------------------------- #
# 1. EXTRAÇÃO
# --------------------------------------------------------------------------- #
def extrair(pausa: float = 1.5) -> None:
    import yfinance as yf

    DIR_RAW.mkdir(parents=True, exist_ok=True)
    fim_exclusivo = (pd.Timestamp(DATA_FIM) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    for ativo in ATIVOS:
        baixado = False
        for simbolo in ativo["aliases"]:
            try:
                hist = yf.Ticker(simbolo).history(
                    start=DATA_INICIO, end=fim_exclusivo,
                    auto_adjust=False, actions=False,
                )
            except Exception as e:  # rede, limite de requisição etc.
                log(f"  [aviso] {simbolo}: falha na requisição ({e})")
                hist = pd.DataFrame()
            if not hist.empty:
                hist = hist.reset_index()
                hist["ticker"] = ativo["ticker"]
                hist["ticker_yahoo"] = simbolo
                hist.to_csv(DIR_RAW / f"{ativo['ticker']}.csv", index=False, encoding="utf-8")
                log(f"  [ok] {ativo['ticker']:<7} via {simbolo:<10} {len(hist):>4} linhas")
                baixado = True
                break
            time.sleep(pausa)
        if not baixado:
            log(f"  [ERRO] {ativo['ticker']}: nenhum símbolo retornou dados")
        time.sleep(pausa)


def ler_brutos() -> pd.DataFrame:
    arquivos = sorted(DIR_RAW.glob("*.csv"))
    if not arquivos:
        raise FileNotFoundError("Nenhum arquivo em data/raw/. Rode sem --offline primeiro.")
    # encoding explícito evita problemas de acentuação entre Windows/Linux
    return pd.concat([pd.read_csv(a, encoding="utf-8") for a in arquivos], ignore_index=True)


# --------------------------------------------------------------------------- #
# 2. LIMPEZA
# --------------------------------------------------------------------------- #
MAPA_COLUNAS = {
    "Date": "data", "Open": "abertura", "High": "maxima", "Low": "minima",
    "Close": "fechamento", "Adj Close": "fechamento_ajustado", "Volume": "volume",
}
COLS_PRECO = ["abertura", "maxima", "minima", "fechamento", "fechamento_ajustado"]


def limpar(bruto: pd.DataFrame) -> pd.DataFrame:
    df = bruto.rename(columns=MAPA_COLUNAS)
    df = df[["data", "ticker", "ticker_yahoo", *COLS_PRECO, "volume"]].copy()
    log(f"Linhas brutas: {len(df)}")

    # Datas: o Yahoo devolve com fuso (ex.: 2021-01-04 00:00:00-03:00).
    # Converte para datetime sem fuso e normaliza para o dia.
    df["data"] = pd.to_datetime(df["data"].astype(str).str[:10], format="%Y-%m-%d", errors="coerce")

    # Valores monetários/numéricos -> float (texto com vírgula vira ponto)
    for c in COLS_PRECO + ["volume"]:
        if df[c].dtype == object:
            df[c] = df[c].astype(str).str.replace(",", ".", regex=False)
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Duplicados (mesmo ativo no mesmo dia)
    dup = df.duplicated(subset=["ticker", "data"], keep="last").sum()
    df = df.drop_duplicates(subset=["ticker", "data"], keep="last")
    log(f"Duplicados removidos: {dup}")

    # Nulos
    nulos = df[["data", "fechamento_ajustado"]].isna().any(axis=1).sum()
    log(f"Nulos por coluna antes do tratamento: {df.isna().sum().to_dict()}")
    df = df.dropna(subset=["data", "fechamento_ajustado"])
    log(f"Linhas sem data ou sem fechamento ajustado removidas: {nulos}")
    df = df.sort_values(["ticker", "data"])
    # Demais preços faltantes: preenche com o último valor válido do MESMO ativo
    df[COLS_PRECO] = df.groupby("ticker")[COLS_PRECO].ffill()
    df["volume"] = df["volume"].fillna(0)

    # Inconsistências
    invalidos = (df[COLS_PRECO] <= 0).any(axis=1) | (df["maxima"] < df["minima"])
    log(f"Linhas com preço <= 0 ou máxima < mínima removidas: {int(invalidos.sum())}")
    df = df.loc[~invalidos]
    sem_negocio = int((df["volume"] == 0).sum())
    log(f"Pregões com volume zero (mantidos e sinalizados): {sem_negocio}")
    df["sem_negocio"] = df["volume"] == 0

    # Recorte temporal obrigatório
    df = df[(df["data"] >= DATA_INICIO) & (df["data"] <= DATA_FIM)]
    log(f"Linhas após limpeza e recorte {DATA_INICIO} a {DATA_FIM}: {len(df)}")
    return df.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# 3. TRANSFORMAÇÃO
# --------------------------------------------------------------------------- #
def transformar(df: pd.DataFrame) -> pd.DataFrame:
    meta = pd.DataFrame(ATIVOS)[["ticker", "empresa", "setor"]]
    df = df.merge(meta, on="ticker", how="left")
    # Volume financeiro (R$) = quantidade negociada x preço de fechamento do dia
    df["volume_financeiro"] = df["volume"] * df["fechamento"]
    df = calcular_medias_moveis(df)
    df = recalcular_janela(df)
    return df


# --------------------------------------------------------------------------- #
# 4. MODELAGEM DIMENSIONAL (esquema estrela)
# --------------------------------------------------------------------------- #
def modelar(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dim_ativo = (df[["ticker", "ticker_yahoo", "empresa", "setor"]]
                 .drop_duplicates("ticker").sort_values("ticker").reset_index(drop=True))
    dim_ativo.insert(0, "id_ativo", range(1, len(dim_ativo) + 1))

    datas = pd.Series(sorted(df["data"].unique()))
    dim_data = pd.DataFrame({"data": datas})
    dim_data["ano"] = dim_data["data"].dt.year
    dim_data["trimestre"] = dim_data["data"].dt.quarter
    dim_data["mes"] = dim_data["data"].dt.month
    dim_data["dia_semana"] = dim_data["data"].dt.day_of_week + 1  # 1 = segunda

    fato = df.merge(dim_ativo[["id_ativo", "ticker"]], on="ticker")
    fato = fato[["id_ativo", "data", "abertura", "maxima", "minima", "fechamento",
                 "fechamento_ajustado", "volume", "volume_financeiro", "retorno_diario",
                 "base100", "drawdown", "sma_21", "sma_50", "sem_negocio"]]
    return dim_ativo, dim_data, fato


# --------------------------------------------------------------------------- #
# 5. CARGA
# --------------------------------------------------------------------------- #
def salvar_csv(dim_ativo, dim_data, fato, resumo) -> None:
    DIR_PROCESSED.mkdir(parents=True, exist_ok=True)
    dim_ativo.to_csv(CSV_DIM_ATIVO, index=False, encoding="utf-8")
    dim_data.to_csv(DIR_PROCESSED / "dim_data.csv", index=False, encoding="utf-8", date_format="%Y-%m-%d")
    fato.to_csv(CSV_FATO, index=False, encoding="utf-8", date_format="%Y-%m-%d", float_format="%.6f")
    resumo.to_csv(CSV_RESUMO, index=False, encoding="utf-8", date_format="%Y-%m-%d", float_format="%.6f")
    log(f"CSVs gravados em {DIR_PROCESSED.relative_to(RAIZ)}/")


def url_postgres() -> str:
    """Lê a URL do banco da variável DATABASE_URL ou do .streamlit/secrets.toml
    (o mesmo arquivo usado pelo app — e que NÃO vai para o GitHub)."""
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    import tomllib
    segredos = RAIZ / ".streamlit" / "secrets.toml"
    with open(segredos, "rb") as f:
        c = tomllib.load(f)["connections"]["postgresql"]
    if "url" in c:
        return c["url"]
    return (f"postgresql+psycopg2://{c['username']}:{c['password']}"
            f"@{c['host']}:{c.get('port', 5432)}/{c['database']}?sslmode=require")


def carregar_postgres(dim_ativo, dim_data, fato) -> None:
    from sqlalchemy import create_engine, text

    engine = create_engine(url_postgres())
    ddl = (RAIZ / "sql" / "schema.sql").read_text(encoding="utf-8")
    with engine.begin() as con:
        for comando in [c.strip() for c in ddl.split(";") if c.strip()]:
            con.execute(text(comando))
    dim_ativo.to_sql("dim_ativo", engine, if_exists="append", index=False)
    dim_data.to_sql("dim_data", engine, if_exists="append", index=False)
    fato.to_sql("fato_cotacao", engine, if_exists="append", index=False, chunksize=2000, method="multi")
    log(f"PostgreSQL: {len(fato)} linhas carregadas em fato_cotacao")


# --------------------------------------------------------------------------- #
def main() -> None:
    p = argparse.ArgumentParser(description="ETL de cotações B3 (2021-2023)")
    p.add_argument("--offline", action="store_true", help="não chama a API; usa data/raw/")
    p.add_argument("--postgres", action="store_true", help="carrega também no PostgreSQL")
    a = p.parse_args()

    log("== 1. Extração ==")
    if not a.offline:
        extrair()
    bruto = ler_brutos()

    log("== 2. Limpeza ==")
    limpo = limpar(bruto)

    log("== 3. Transformação ==")
    tratado = transformar(limpo)
    resumo = resumo_por_ativo(tratado)
    log(resumo[["ticker", "retorno_acumulado", "volatilidade_anual", "drawdown_maximo"]]
        .round(4).to_string(index=False))

    log("== 4. Modelagem ==")
    dim_ativo, dim_data, fato = modelar(tratado)
    log(f"dim_ativo: {len(dim_ativo)} | dim_data: {len(dim_data)} | fato_cotacao: {len(fato)}")

    log("== 5. Carga ==")
    salvar_csv(dim_ativo, dim_data, fato, resumo)
    if a.postgres:
        carregar_postgres(dim_ativo, dim_data, fato)

    (RAIZ / "docs" / "relatorio_etl.txt").write_text("\n".join(RELATORIO), encoding="utf-8")
    print("Relatório salvo em docs/relatorio_etl.txt")


if __name__ == "__main__":
    main()
