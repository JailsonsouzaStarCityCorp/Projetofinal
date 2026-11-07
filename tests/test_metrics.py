"""Testes das fórmulas financeiras (rodar com: python -m pytest)."""
import numpy as np
import pandas as pd

from src.metrics import cruzamentos_sma, recalcular_janela, resumo_por_ativo


def serie(precos, ticker="TESTE3"):
    datas = pd.bdate_range("2023-01-02", periods=len(precos))
    return pd.DataFrame({"data": datas, "ticker": ticker, "empresa": "Teste", "setor": "Financeiro",
                         "fechamento_ajustado": precos, "volume_financeiro": 1e6})


def test_base100_e_drawdown():
    d = recalcular_janela(serie([10, 12, 9, 15]))
    assert d["base100"].tolist() == [100, 120, 90, 150]
    assert np.isclose(d["drawdown"].min(), 9 / 12 - 1)  # -25% do pico de 12
    assert d["drawdown"].iloc[-1] == 0                    # novo topo


def test_retorno_acumulado_e_volatilidade():
    precos = [100, 110, 99, 108.9]
    r = resumo_por_ativo(recalcular_janela(serie(precos))).iloc[0]
    assert np.isclose(r["retorno_acumulado"], 0.089)
    diarios = pd.Series(precos).pct_change().dropna()
    assert np.isclose(r["volatilidade_anual"], diarios.std() * np.sqrt(252))


def test_cruzamento_sma():
    d = serie([1] * 4)
    d["sma_21"] = [1, 3, 3, 1]
    d["sma_50"] = [2, 2, 2, 2]
    cz = cruzamentos_sma(d)
    assert cz["tipo"].tolist() == ["Cruz dourada (alta)", "Cruz da morte (baixa)"]
