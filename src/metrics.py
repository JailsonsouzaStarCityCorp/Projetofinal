"""Funções de cálculo financeiro compartilhadas entre o ETL e o Data App.

Convenções:
- Retornos em fração decimal (0.05 = 5%). A conversão para % é feita só na exibição.
- Todas as métricas são calculadas por ativo (groupby 'ticker').
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import DIAS_UTEIS_ANO


def calcular_medias_moveis(df: pd.DataFrame, janelas=(21, 50)) -> pd.DataFrame:
    """SMA sobre o fechamento ajustado. Calculada na série COMPLETA para que o
    filtro de datas do app não 'perca' os primeiros dias de aquecimento."""
    df = df.sort_values(["ticker", "data"]).copy()
    g = df.groupby("ticker")["fechamento_ajustado"]
    for j in janelas:
        df[f"sma_{j}"] = g.transform(lambda s, j=j: s.rolling(j, min_periods=j).mean())
    return df


def recalcular_janela(df: pd.DataFrame) -> pd.DataFrame:
    """Recalcula as métricas que dependem do ponto de partida da janela
    (retorno diário, Base 100, pico e drawdown). Usada após o filtro de datas."""
    df = df.sort_values(["ticker", "data"]).copy()
    g = df.groupby("ticker")["fechamento_ajustado"]
    df["retorno_diario"] = g.pct_change()
    df["base100"] = df["fechamento_ajustado"] / g.transform("first") * 100
    df["pico_historico"] = g.cummax()
    df["drawdown"] = df["fechamento_ajustado"] / df["pico_historico"] - 1
    return df


def resumo_por_ativo(df: pd.DataFrame, taxa_livre_risco: float = 0.0) -> pd.DataFrame:
    """Tabela-resumo com uma linha por ativo.

    df precisa ter passado por recalcular_janela().
    taxa_livre_risco: % a.a. em fração (0.10 = 10% a.a.). Com 0 temos o
    'Sharpe empírico' pedido no enunciado (retorno/risco).
    """
    linhas = []
    for ticker, d in df.sort_values("data").groupby("ticker"):
        r = d["retorno_diario"].dropna()
        if len(d) < 2 or r.empty:
            continue
        preco_ini = d["fechamento_ajustado"].iloc[0]
        preco_fim = d["fechamento_ajustado"].iloc[-1]
        ret_acum = preco_fim / preco_ini - 1
        n = len(r)
        ret_anual = (1 + ret_acum) ** (DIAS_UTEIS_ANO / n) - 1
        vol_anual = r.std(ddof=1) * np.sqrt(DIAS_UTEIS_ANO)
        sharpe = (ret_anual - taxa_livre_risco) / vol_anual if vol_anual > 0 else np.nan
        idx_fundo = d["drawdown"].idxmin()
        linhas.append({
            "ticker": ticker,
            "empresa": d["empresa"].iloc[0],
            "setor": d["setor"].iloc[0],
            "data_inicio": d["data"].iloc[0],
            "data_fim": d["data"].iloc[-1],
            "preco_inicial": preco_ini,
            "preco_final": preco_fim,
            "retorno_acumulado": ret_acum,
            "retorno_anualizado": ret_anual,
            "volatilidade_anual": vol_anual,
            "sharpe": sharpe,
            "drawdown_maximo": d["drawdown"].min(),
            "data_fundo_drawdown": d.loc[idx_fundo, "data"],
            "retorno_medio_diario": r.mean(),
            "assimetria": r.skew(),
            "curtose_excesso": r.kurt(),
            "var_95_diario": r.quantile(0.05),
            "pior_dia": r.min(),
            "melhor_dia": r.max(),
            "volume_financeiro_medio": d["volume_financeiro"].mean(),
            "pregoes": len(d),
        })
    return pd.DataFrame(linhas)


def cruzamentos_sma(d: pd.DataFrame) -> pd.DataFrame:
    """Datas em que a SMA 21 cruza a SMA 50 (um único ativo).
    'Cruz dourada' = SMA21 passa para cima; 'Cruz da morte' = passa para baixo."""
    d = d.dropna(subset=["sma_21", "sma_50"]).sort_values("data")
    acima = (d["sma_21"] > d["sma_50"]).astype(int)
    mudanca = acima.diff()
    out = d.loc[mudanca != 0].iloc[1:].copy() if len(d) else d
    out["tipo"] = np.where(acima.loc[out.index] == 1, "Cruz dourada (alta)", "Cruz da morte (baixa)")
    return out[["data", "fechamento_ajustado", "tipo"]]
