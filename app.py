"""Data App — Performance de Mercado de Ações na B3 (2021-2023)

Linha 2 do Projeto Avaliativo Final — Visualização de Dados e BI [T2]
Executar localmente:  streamlit run app.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.config import (ATIVOS, CORES_SETOR, CSV_DIM_ATIVO, CSV_FATO, SETORES,
                        SIMBOLOS_SETOR)
from src.metrics import cruzamentos_sma, recalcular_janela, resumo_por_ativo

st.set_page_config(
    page_title="B3 | Performance de Ações 2021-2023",
    page_icon="📈",
    layout="wide",
)

# Tokens de texto (rótulos nunca usam a cor da série)
TEXTO_SEC = "#52514e"
TEXTO_MUTED = "#898781"
COR_PRECO = "#52514e"
COR_SMA21 = "#2a78d6"
COR_SMA50 = "#eb6834"
NOME_EMPRESA = {a["ticker"]: a["empresa"] for a in ATIVOS}

SQL_APP = """
SELECT f.data, a.ticker, a.empresa, a.setor,
       f.abertura, f.maxima, f.minima, f.fechamento, f.fechamento_ajustado,
       f.volume, f.volume_financeiro, f.sma_21, f.sma_50
FROM fato_cotacao f
JOIN dim_ativo a USING (id_ativo)
ORDER BY a.ticker, f.data
"""
COLS_NUM = ["abertura", "maxima", "minima", "fechamento", "fechamento_ajustado",
            "volume", "volume_financeiro", "sma_21", "sma_50"]


# =========================================================================== #
# FORMATAÇÃO (padrão brasileiro)
# =========================================================================== #
def _br(txt: str) -> str:
    return txt.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x: float, casas: int = 1, sinal: bool = True) -> str:
    if pd.isna(x):
        return "—"
    return _br(f"{x * 100:{'+' if sinal else ''},.{casas}f}%")


def pp(x: float) -> str:
    """Diferença em pontos percentuais."""
    return _br(f"{x * 100:+,.1f}") + " p.p."


def delta_universo(diff: float) -> str | None:
    """Texto do delta vs. universo; None quando a seleção é o próprio universo."""
    return None if abs(diff) < 1e-9 else f"{pp(diff)} vs. universo"


def brl(x: float) -> str:
    if pd.isna(x):
        return "—"
    if abs(x) >= 1e9:
        return _br(f"R$ {x / 1e9:,.2f} bi")
    if abs(x) >= 1e6:
        return _br(f"R$ {x / 1e6:,.1f} mi")
    return _br(f"R$ {x:,.2f}")


def estilo(fig: go.Figure, altura: int = 460) -> go.Figure:
    fig.update_layout(
        height=altura,
        separators=",.",  # vírgula decimal, ponto de milhar
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif', size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text=""),
        margin=dict(l=10, r=20, t=40, b=10),
        hoverlabel=dict(font_size=13),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(137,135,129,0.25)", zeroline=False)
    return fig


def rotular_fim(fig: go.Figure, d: pd.DataFrame, y: str) -> None:
    """Rótulo direto (ticker) no último ponto de cada linha, com anti-colisão."""
    ult = d.sort_values("data").groupby("ticker").tail(1).sort_values(y)
    if ult.empty:
        return
    faixa = d[y].max() - d[y].min()
    folga = faixa / 26 if faixa > 0 else 1
    posicoes: list[float] = []
    for v in ult[y]:
        posicoes.append(v if not posicoes else max(v, posicoes[-1] + folga))
    for (_, r), p in zip(ult.iterrows(), posicoes):
        fig.add_annotation(x=r["data"], y=p, text=r["ticker"], showarrow=False,
                           xanchor="left", xshift=6, font=dict(size=11, color=TEXTO_SEC))
    fig.update_layout(margin=dict(r=75))


def bloco_insight(insight: str, acao: str) -> None:
    with st.container(border=True):
        st.markdown(f"💡 **Insight:** {insight}")
        st.markdown(f"🎯 **Ação sugerida:** {acao}")


# =========================================================================== #
# DADOS — conexão resiliente (PostgreSQL na nuvem -> fallback CSV)
# =========================================================================== #
@st.cache_data(ttl=3600, show_spinner="Carregando cotações da B3...")
def carregar_dados() -> tuple[pd.DataFrame, str, str]:
    try:
        conn = st.connection("postgresql", type="sql")
        df = conn.query(SQL_APP, ttl=3600)
        if df.empty:
            raise ValueError("tabela fato_cotacao vazia")
        origem, detalhe = "PostgreSQL na nuvem (Supabase)", "conexão ativa"
    except Exception as erro:  # sem secrets, banco fora do ar, tabela ausente...
        fato = pd.read_csv(CSV_FATO, encoding="utf-8")
        dim = pd.read_csv(CSV_DIM_ATIVO, encoding="utf-8")
        df = fato.merge(dim[["id_ativo", "ticker", "empresa", "setor"]], on="id_ativo")
        origem = "CSV local (contingência)"
        detalhe = f"banco indisponível: {type(erro).__name__}"
    df["data"] = pd.to_datetime(df["data"])
    for c in COLS_NUM:  # NUMERIC do Postgres chega como Decimal
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    return df.sort_values(["ticker", "data"]).reset_index(drop=True), origem, detalhe


@st.cache_data(ttl=3600, show_spinner=False)
def preparar_janela(df: pd.DataFrame, tickers: tuple, ini, fim) -> pd.DataFrame:
    d = df[df["ticker"].isin(tickers) &
           (df["data"] >= pd.Timestamp(ini)) & (df["data"] <= pd.Timestamp(fim))]
    return recalcular_janela(d)


@st.cache_data(ttl=3600, show_spinner=False)
def resumir(d: pd.DataFrame, rf: float) -> pd.DataFrame:
    return resumo_por_ativo(d, taxa_livre_risco=rf)


try:
    base, ORIGEM, DETALHE = carregar_dados()
except FileNotFoundError:
    st.error("Nenhuma fonte de dados disponível: o banco não respondeu e os CSVs de "
             "contingência não foram encontrados em `data/processed/`.\n\n"
             "Rode o ETL a partir da raiz do projeto: `python -m etl.etl_b3`")
    st.stop()

DATA_MIN = base["data"].min().date()
DATA_MAX = base["data"].max().date()
SETORES_DISP = [s for s in SETORES if s in base["setor"].unique()]
TICKERS_POR_SETOR = {s: sorted(base.loc[base["setor"] == s, "ticker"].unique()) for s in SETORES_DISP}


# =========================================================================== #
# ESTADO DOS FILTROS (st.session_state)
# =========================================================================== #
def filtros_padrao() -> dict:
    return {
        "f_setores": SETORES_DISP.copy(),
        "f_ativos": sorted(base["ticker"].unique()),
        "f_periodo": (DATA_MIN, DATA_MAX),
        "f_rf": 0.0,
    }


for chave, valor in filtros_padrao().items():
    st.session_state.setdefault(chave, valor)


def resetar_filtros() -> None:
    for chave, valor in filtros_padrao().items():
        st.session_state[chave] = valor
    st.session_state.pop("f_ativo_sma", None)
    st.session_state.pop("f_ativos_dist", None)
    st.session_state.pop("f_ativos_dd", None)


def ao_mudar_setor() -> None:
    """Filtro cruzado: trocar os setores reseleciona os ativos desses setores."""
    st.session_state["f_ativos"] = [t for s in st.session_state["f_setores"]
                                    for t in TICKERS_POR_SETOR.get(s, [])]


def definir_periodo(ini, fim) -> None:
    st.session_state["f_periodo"] = (max(ini, DATA_MIN), min(fim, DATA_MAX))


# =========================================================================== #
# BARRA LATERAL
# =========================================================================== #
with st.sidebar:
    st.header("🎛️ Filtros")
    st.button("🔄 Resetar filtros", on_click=resetar_filtros, width="stretch")

    st.multiselect("Setores", SETORES_DISP, key="f_setores", on_change=ao_mudar_setor,
                   help="Ao mudar os setores, a lista de ativos é atualizada.")

    opcoes_ativos = [t for s in st.session_state["f_setores"] for t in TICKERS_POR_SETOR.get(s, [])]
    # Remove do estado ativos que deixaram de existir nas opções (evita erro do widget)
    st.session_state["f_ativos"] = [t for t in st.session_state["f_ativos"] if t in opcoes_ativos]
    st.multiselect("Ativos", opcoes_ativos, key="f_ativos",
                   format_func=lambda t: f"{t} — {NOME_EMPRESA.get(t, '')}")

    st.markdown("**Período**")
    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)
    c1.button("Período completo", on_click=definir_periodo, args=(DATA_MIN, DATA_MAX), width="stretch")
    for col, ano in zip((c2, c3, c4), (2021, 2022, 2023)):
        col.button(str(ano), on_click=definir_periodo,
                   args=(pd.Timestamp(f"{ano}-01-01").date(), pd.Timestamp(f"{ano}-12-31").date()),
                   width="stretch")
    st.slider("Janela de análise", min_value=DATA_MIN, max_value=DATA_MAX,
              key="f_periodo", format="DD/MM/YYYY", label_visibility="collapsed")

    st.number_input("Taxa livre de risco (% a.a.)", min_value=0.0, max_value=30.0, step=0.5,
                    key="f_rf", format="%.1f", help="0% = Sharpe empírico (retorno ÷ volatilidade), como pede o "
                                     "enunciado. Informe o CDI médio do período para o Sharpe clássico.")

    st.divider()
    icone = "☁️" if ORIGEM.startswith("PostgreSQL") else "💾"
    st.caption(f"{icone} **Fonte:** {ORIGEM}  \n{DETALHE}")
    st.caption(f"Dados de {DATA_MIN:%d/%m/%Y} a {DATA_MAX:%d/%m/%Y} · Yahoo Finance (B3, sufixo .SA)")

ativos_sel = tuple(st.session_state["f_ativos"])
ini, fim = st.session_state["f_periodo"]
rf = st.session_state["f_rf"] / 100

# =========================================================================== #
# CABEÇALHO
# =========================================================================== #
st.title("📈 Performance de Ações na B3 — 2021 a 2023")
st.markdown(
    "**Contexto:** se um investidor tivesse aplicado o mesmo valor em cada uma das 12 ações "
    "líquidas do universo no primeiro pregão de 2021, como estaria a carteira no fim de 2023, "
    "e qual risco teria enfrentado no caminho? Use os filtros à esquerda para recortar ativos, "
    "setores e período."
)

if not ativos_sel:
    st.warning("Selecione ao menos um ativo na barra lateral para iniciar a análise.")
    st.stop()

d = preparar_janela(base, ativos_sel, ini, fim)
if d.groupby("ticker").size().min() < 30:
    st.warning("A janela escolhida tem menos de 30 pregões: as estatísticas de risco ficam "
               "pouco confiáveis. Amplie o período.")
    if d["data"].nunique() < 2:
        st.stop()

res = resumir(d, rf)
universo = resumir(preparar_janela(base, tuple(sorted(base["ticker"].unique())), ini, fim), rf)

# =========================================================================== #
# KPIs
# =========================================================================== #
ret_medio = res["retorno_acumulado"].mean()
vol_media = res["volatilidade_anual"].mean()
dd_medio = res["drawdown_maximo"].mean()
melhor = res.loc[res["retorno_acumulado"].idxmax()]
pior = res.loc[res["retorno_acumulado"].idxmin()]

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Retorno médio da carteira", pct(ret_medio),
          delta=delta_universo(ret_medio - universo["retorno_acumulado"].mean()),
          help="Carteira de pesos iguais, sem rebalanceamento (buy & hold) = média simples "
               "dos retornos acumulados dos ativos selecionados.")
k2.metric("Ativo destaque", melhor["ticker"], delta=pct(melhor["retorno_acumulado"]),
          help=f"{melhor['empresa']} — maior retorno acumulado na janela.")
k3.metric("Menor performance", pior["ticker"], delta=pct(pior["retorno_acumulado"]),
          help=f"{pior['empresa']} — menor retorno acumulado na janela.")
k4.metric("Volatilidade anualizada média", pct(vol_media, sinal=False) + " a.a.",
          delta=delta_universo(vol_media - universo["volatilidade_anual"].mean()),
          delta_color="inverse", help="Desvio-padrão dos retornos diários × √252.")
k5.metric("Drawdown máximo médio", pct(dd_medio),
          delta=delta_universo(dd_medio - universo["drawdown_maximo"].mean()),
          help="Média das maiores quedas a partir do pico de cada ativo. Delta positivo = "
               "quedas menores que as do universo.")
st.caption(f"Janela: {ini:%d/%m/%Y} a {fim:%d/%m/%Y} · {len(ativos_sel)} ativo(s) · "
           f"{d['data'].nunique()} pregões · 'universo' = os 12 ativos no mesmo período")

# =========================================================================== #
# ABAS
# =========================================================================== #
abas = st.tabs(["📈 Rentabilidade", "⚖️ Risco x Retorno", "📊 Retornos diários",
                "📉 Drawdown", "🧭 Médias móveis", "🔗 Correlação",
                "🗂️ Dados & exportação", "ℹ️ Metodologia"])

# --------------------------------------------------------------------------- #
# 1. RENTABILIDADE BASE 100
# --------------------------------------------------------------------------- #
with abas[0]:
    st.subheader("Quanto valeria R$ 100 investidos em cada ativo?")
    st.caption("Série normalizada: cada ativo começa em 100 no primeiro pregão da janela "
               "(fechamento ajustado por proventos e desdobramentos).")
    fig = px.line(d, x="data", y="base100", color="setor", line_group="ticker",
                  hover_name="ticker", color_discrete_map=CORES_SETOR,
                  category_orders={"setor": SETORES},
                  hover_data={"setor": True, "base100": ":.1f", "data": "|%d/%m/%Y"},
                  labels={"base100": "Base 100", "data": "", "setor": "Setor"})
    fig.update_traces(line_width=2)
    fig.add_hline(y=100, line_dash="dot", line_color=TEXTO_MUTED,
                  annotation_text="nível inicial (100)", annotation_position="bottom left",
                  annotation_font_color=TEXTO_MUTED)
    rotular_fim(fig, d, "base100")
    st.plotly_chart(estilo(fig), width="stretch")

    ranking = res.sort_values("retorno_acumulado")
    fig_r = px.bar(ranking, x="retorno_acumulado", y="ticker", color="setor", orientation="h",
                   color_discrete_map=CORES_SETOR, category_orders={"setor": SETORES},
                   text=ranking["retorno_acumulado"].map(pct),
                   hover_data={"empresa": True, "retorno_acumulado": ":.1%"},
                   labels={"retorno_acumulado": "Retorno acumulado", "ticker": "", "setor": "Setor"})
    fig_r.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0)
    fig_r.update_xaxes(tickformat=".0%")
    fig_r.update_yaxes(categoryorder="array", categoryarray=ranking["ticker"].tolist())
    st.plotly_chart(estilo(fig_r, altura=max(300, 34 * len(ranking) + 80)), width="stretch")

    acima = int((res["retorno_acumulado"] > 0).sum())
    setor_top = res.groupby("setor")["retorno_acumulado"].mean().idxmax()
    bloco_insight(
        f"**{melhor['ticker']}** ({melhor['empresa']}) transformou R$ 100 em "
        f"**{brl(100 * (1 + melhor['retorno_acumulado']))}**, enquanto **{pior['ticker']}** "
        f"terminou em **{brl(100 * (1 + pior['retorno_acumulado']))}**. {acima} de {len(res)} "
        f"ativos fecharam a janela acima do nível 100, e o setor com maior retorno médio foi "
        f"**{setor_top}**.",
        "A diferença entre o melhor e o pior ativo "
        f"({pp(melhor['retorno_acumulado'] - pior['retorno_acumulado'])}) mostra o peso da "
        "seleção de ativos. Antes de qualquer conclusão, compare com o risco assumido na aba "
        "**Risco x Retorno**: retorno passado não garante retorno futuro.",
    )

# --------------------------------------------------------------------------- #
# 2. RISCO x RETORNO
# --------------------------------------------------------------------------- #
with abas[1]:
    st.subheader("Quem entregou mais retorno por unidade de risco?")
    st.caption("Eixo X: volatilidade anualizada. Eixo Y: retorno acumulado. Tamanho da bolha: "
               "volume financeiro médio diário. As linhas tracejadas marcam as médias da seleção.")
    fig = px.scatter(res, x="volatilidade_anual", y="retorno_acumulado", size="volume_financeiro_medio",
                     color="setor", symbol="setor", text="ticker", size_max=30,
                     color_discrete_map=CORES_SETOR, symbol_map=SIMBOLOS_SETOR,
                     category_orders={"setor": SETORES}, hover_name="empresa",
                     hover_data={"volatilidade_anual": ":.1%", "retorno_acumulado": ":.1%",
                                 "sharpe": ":.2f", "volume_financeiro_medio": ":,.0f", "ticker": False},
                     labels={"volatilidade_anual": "Volatilidade anualizada (% a.a.)",
                             "retorno_acumulado": "Retorno acumulado (%)", "sharpe": "Sharpe",
                             "volume_financeiro_medio": "Vol. financeiro médio (R$)", "setor": "Setor"})
    fig.update_traces(textposition="top center", textfont=dict(color=TEXTO_SEC, size=11),
                      marker=dict(line=dict(width=1.5, color="white"), opacity=0.85))
    fig.add_vline(x=vol_media, line_dash="dash", line_color=TEXTO_MUTED)
    fig.add_hline(y=ret_medio, line_dash="dash", line_color=TEXTO_MUTED)
    fig.update_xaxes(tickformat=".1%")
    folga_y = (res["retorno_acumulado"].max() - res["retorno_acumulado"].min()) * 0.15 + 0.05
    fig.update_yaxes(tickformat=".0%", range=[res["retorno_acumulado"].min() - folga_y,
                                              res["retorno_acumulado"].max() + folga_y])
    for texto, xa, ya, xan, yan in [("Mais retorno · menos risco", 0.01, 0.99, "left", "top"),
                                    ("Mais retorno · mais risco", 0.99, 0.99, "right", "top"),
                                    ("Menos retorno · menos risco", 0.01, 0.01, "left", "bottom"),
                                    ("Menos retorno · mais risco", 0.99, 0.01, "right", "bottom")]:
        fig.add_annotation(xref="paper", yref="paper", x=xa, y=ya, text=texto, showarrow=False,
                           xanchor=xan, yanchor=yan, font=dict(size=11, color=TEXTO_MUTED))
    st.plotly_chart(estilo(fig, 520), width="stretch")

    tab_sharpe = (res.sort_values("sharpe", ascending=False)
                  [["ticker", "empresa", "setor", "retorno_anualizado", "volatilidade_anual", "sharpe"]])
    st.dataframe(
        tab_sharpe, hide_index=True, width="stretch",
        column_config={
            "ticker": "Ativo", "empresa": "Empresa", "setor": "Setor",
            "retorno_anualizado": st.column_config.NumberColumn("Retorno anualizado", format="percent"),
            "volatilidade_anual": st.column_config.NumberColumn("Volatilidade a.a.", format="percent"),
            "sharpe": st.column_config.ProgressColumn(
                "Índice de Sharpe", format="%.2f",
                min_value=float(min(0, tab_sharpe["sharpe"].min())),
                max_value=float(max(0.01, tab_sharpe["sharpe"].max()))),
        })
    top_s = tab_sharpe.iloc[0]
    q1 = res[(res["retorno_acumulado"] > ret_medio) & (res["volatilidade_anual"] < vol_media)]
    bloco_insight(
        f"A melhor relação retorno/risco foi de **{top_s['ticker']}** (Sharpe "
        f"{_br(f'{top_s.sharpe:.2f}')}: retorno de {pct(top_s['retorno_anualizado'])} a.a. com "
        f"volatilidade de {pct(top_s['volatilidade_anual'], sinal=False)} a.a.). "
        + (f"No quadrante ideal (acima da média de retorno e abaixo da média de risco) ficaram: "
           f"**{', '.join(q1['ticker'])}**." if len(q1) else
           "Nenhum ativo ficou simultaneamente acima da média de retorno e abaixo da média de risco."),
        "Ativos no quadrante superior esquerdo merecem análise fundamentalista mais profunda; os do "
        "inferior direito pedem revisão de tese. O Sharpe é uma medida histórica e muda conforme "
        "a janela: teste 2021, 2022 e 2023 separadamente nos botões de período.",
    )

# --------------------------------------------------------------------------- #
# 3. DISTRIBUIÇÃO DOS RETORNOS DIÁRIOS
# --------------------------------------------------------------------------- #
with abas[2]:
    st.subheader("Como se distribuem os retornos diários?")
    st.caption("Histograma dos retornos diários (%) com boxplot marginal. Caudas longas indicam "
               "dias extremos mais frequentes do que uma distribuição normal preveria.")
    modo = st.radio("Comparar por", ["Setor", "Ativos (até 3)"], horizontal=True, key="f_modo_dist")
    dr = d.dropna(subset=["retorno_diario"]).assign(retorno_pct=lambda x: x["retorno_diario"] * 100)
    if modo == "Setor":
        fig = px.histogram(dr, x="retorno_pct", color="setor", marginal="box", nbins=120,
                           barmode="overlay", opacity=0.55, color_discrete_map=CORES_SETOR,
                           category_orders={"setor": SETORES},
                           labels={"retorno_pct": "Retorno diário (%)", "setor": "Setor"})
    else:
        padrao = [t for t in [melhor["ticker"], pior["ticker"]] if t in ativos_sel]
        st.session_state["f_ativos_dist"] = [t for t in st.session_state.get("f_ativos_dist", padrao)
                                             if t in ativos_sel] or padrao
        escolha = st.multiselect("Ativos", list(ativos_sel), key="f_ativos_dist", max_selections=3)
        cores3 = dict(zip(sorted(escolha), ["#2a78d6", "#eb6834", "#1baf7a"]))
        fig = px.histogram(dr[dr["ticker"].isin(escolha)], x="retorno_pct", color="ticker",
                           marginal="box", nbins=100, barmode="overlay", opacity=0.55,
                           color_discrete_map=cores3,
                           labels={"retorno_pct": "Retorno diário (%)", "ticker": "Ativo"})
    fig.update_yaxes(title_text="Frequência (dias)", row=1, col=1)
    fig.add_vline(x=0, line_color=TEXTO_MUTED, line_width=1)
    st.plotly_chart(estilo(fig, 500), width="stretch")

    est = res[["ticker", "setor", "retorno_medio_diario", "volatilidade_anual", "assimetria",
               "curtose_excesso", "var_95_diario", "pior_dia", "melhor_dia"]].sort_values("curtose_excesso",
                                                                                         ascending=False)
    st.dataframe(est, hide_index=True, width="stretch", column_config={
        "ticker": "Ativo", "setor": "Setor",
        "retorno_medio_diario": st.column_config.NumberColumn("Média diária", format="percent"),
        "volatilidade_anual": st.column_config.NumberColumn("Volatilidade a.a.", format="percent"),
        "assimetria": st.column_config.NumberColumn("Assimetria", format="%.2f"),
        "curtose_excesso": st.column_config.NumberColumn("Curtose (excesso)", format="%.2f"),
        "var_95_diario": st.column_config.NumberColumn("VaR 95% (1 dia)", format="percent"),
        "pior_dia": st.column_config.NumberColumn("Pior dia", format="percent"),
        "melhor_dia": st.column_config.NumberColumn("Melhor dia", format="percent"),
    })
    caudas = int((res["curtose_excesso"] > 0).sum())
    mais_cauda = est.iloc[0]
    neg = int((res["assimetria"] < 0).sum())
    bloco_insight(
        f"{caudas} de {len(res)} ativos têm curtose em excesso positiva (caudas mais pesadas que a "
        f"normal); o caso mais extremo é **{mais_cauda['ticker']}** (curtose "
        f"{_br(f'{mais_cauda.curtose_excesso:.1f}')}, pior dia de {pct(mais_cauda['pior_dia'])}). "
        f"{neg} ativo(s) apresentam assimetria negativa, isto é, quedas extremas mais intensas "
        "que as altas extremas.",
        "Não use apenas a volatilidade como medida de risco: em ativos de cauda pesada, o VaR "
        "histórico e o pior dia dão uma noção mais realista da perda possível em um pregão.",
    )

# --------------------------------------------------------------------------- #
# 4. DRAWDOWN
# --------------------------------------------------------------------------- #
with abas[3]:
    st.subheader("Qual foi a maior queda a partir do topo?")
    st.caption("Drawdown = queda percentual do preço em relação ao maior preço já atingido "
               "dentro da janela. Zero = o ativo está no seu topo.")
    res_dd = res.sort_values("drawdown_maximo", ascending=False)  # mais resiliente primeiro
    resiliente, fragil = res_dd.iloc[0], res_dd.iloc[-1]
    padrao_dd = list(dict.fromkeys([resiliente["ticker"], fragil["ticker"]]))
    st.session_state["f_ativos_dd"] = [t for t in st.session_state.get("f_ativos_dd", padrao_dd)
                                       if t in ativos_sel] or padrao_dd
    escolha_dd = st.multiselect("Ativos no gráfico de área (até 4)", list(ativos_sel),
                                key="f_ativos_dd", max_selections=4)
    dd = d[d["ticker"].isin(escolha_dd)]
    fig = px.line(dd, x="data", y="drawdown", color="setor", line_group="ticker", hover_name="ticker",
                  color_discrete_map=CORES_SETOR, category_orders={"setor": SETORES},
                  hover_data={"drawdown": ":.1%", "data": "|%d/%m/%Y", "setor": True},
                  labels={"drawdown": "Queda desde o topo", "data": "", "setor": "Setor"})
    fig.update_traces(fill="tozeroy", line_width=2)
    fig.update_yaxes(tickformat=".0%")
    rotular_fim(fig, dd, "drawdown")
    st.plotly_chart(estilo(fig), width="stretch")

    fig_b = px.bar(res_dd, x="ticker", y="drawdown_maximo", color="setor",
                   color_discrete_map=CORES_SETOR, category_orders={"setor": SETORES},
                   text=res_dd["drawdown_maximo"].map(lambda v: pct(v, 0)),
                   hover_data={"empresa": True, "data_fundo_drawdown": "|%d/%m/%Y",
                               "drawdown_maximo": ":.1%"},
                   labels={"drawdown_maximo": "Drawdown máximo", "ticker": "",
                           "data_fundo_drawdown": "Data do fundo", "setor": "Setor"})
    fig_b.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0)
    fig_b.update_yaxes(tickformat=".0%")
    fig_b.update_xaxes(categoryorder="array", categoryarray=res_dd["ticker"].tolist())
    fig_b = estilo(fig_b, 400)
    fig_b.update_layout(legend=dict(y=-0.22, yanchor="top"))  # legenda abaixo: barras partem do topo
    st.plotly_chart(fig_b, width="stretch")
    bloco_insight(
        f"O ativo mais resiliente foi **{resiliente['ticker']}**, cuja pior queda foi de "
        f"{pct(resiliente['drawdown_maximo'])}. O mais exposto foi **{fragil['ticker']}**, que chegou "
        f"a {pct(fragil['drawdown_maximo'])} do topo em {fragil['data_fundo_drawdown']:%d/%m/%Y}. "
        f"Para voltar ao topo, uma queda de {pct(fragil['drawdown_maximo'], 0)} exige alta de "
        f"{pct(1 / (1 + fragil['drawdown_maximo']) - 1, 0)}.",
        "Defina o tamanho de cada posição de acordo com a queda que você aceita suportar. Um "
        "drawdown histórico profundo indica o que pode voltar a acontecer, não um limite.",
    )

# --------------------------------------------------------------------------- #
# 5. MÉDIAS MÓVEIS
# --------------------------------------------------------------------------- #
with abas[4]:
    st.subheader("O preço está acima ou abaixo da tendência?")
    st.caption("Fechamento ajustado com médias móveis simples de 21 pregões (≈ 1 mês, curto "
               "prazo) e 50 pregões (≈ 2,5 meses, médio prazo).")
    if st.session_state.get("f_ativo_sma") not in ativos_sel:
        st.session_state["f_ativo_sma"] = ativos_sel[0]
    ativo = st.selectbox("Ativo", list(ativos_sel), key="f_ativo_sma",
                         format_func=lambda t: f"{t} — {NOME_EMPRESA.get(t, '')}")
    s = d[d["ticker"] == ativo].sort_values("data")
    longo = s.melt(id_vars="data", value_vars=["fechamento_ajustado", "sma_21", "sma_50"],
                   var_name="serie", value_name="preco")
    nomes = {"fechamento_ajustado": "Fechamento ajustado", "sma_21": "SMA 21", "sma_50": "SMA 50"}
    longo["serie"] = longo["serie"].map(nomes)
    fig = px.line(longo, x="data", y="preco", color="serie",
                  color_discrete_map={"Fechamento ajustado": COR_PRECO, "SMA 21": COR_SMA21,
                                      "SMA 50": COR_SMA50},
                  hover_data={"preco": ":.2f", "data": "|%d/%m/%Y"},
                  labels={"preco": "Preço (R$)", "data": "", "serie": ""})
    fig.update_traces(line_width=2)
    fig.for_each_trace(lambda t: t.update(line_width=1.5) if t.name == "Fechamento ajustado" else None)
    cz = cruzamentos_sma(s)
    for tipo, simb, cor in [("Cruz dourada (alta)", "triangle-up", "#0ca30c"),
                            ("Cruz da morte (baixa)", "triangle-down", "#d03b3b")]:
        pts = cz[cz["tipo"] == tipo]
        if len(pts):
            fig.add_trace(go.Scatter(x=pts["data"], y=pts["fechamento_ajustado"], mode="markers",
                                     name=tipo, marker=dict(symbol=simb, size=12, color=cor,
                                                            line=dict(width=1.5, color="white")),
                                     hovertemplate="%{x|%d/%m/%Y}<br>" + tipo + "<extra></extra>"))
    st.plotly_chart(estilo(fig), width="stretch")

    valid = s.dropna(subset=["sma_50"])
    dias_acima = (valid["fechamento_ajustado"] > valid["sma_50"]).mean() if len(valid) else np.nan
    ult = s.iloc[-1]
    m1, m2, m3 = st.columns(3)
    m1.metric("Dias acima da SMA 50", pct(dias_acima, 0, sinal=False))
    m2.metric("Preço vs. SMA 50 no fim da janela",
              pct(ult["fechamento_ajustado"] / ult["sma_50"] - 1) if pd.notna(ult["sma_50"]) else "—")
    m3.metric("Cruzamentos SMA21 × SMA50", f"{len(cz)}",
              help="Muitos cruzamentos = mercado lateral; poucos = tendência mais definida.")
    if len(cz):
        u = cz.iloc[-1]
        txt_cz = f"O último cruzamento foi uma **{u['tipo'].lower()}** em {u['data']:%d/%m/%Y}."
    else:
        txt_cz = "Não houve cruzamento entre as médias na janela."
    bloco_insight(
        f"{ativo} passou {pct(dias_acima, 0, sinal=False)} dos pregões acima da SMA 50. {txt_cz}",
        "Use as médias como apoio descritivo para identificar tendência, junto com fundamentos e "
        "gestão de risco. Sozinhas, elas não constituem recomendação de compra ou venda.",
    )

# --------------------------------------------------------------------------- #
# 6. CORRELAÇÃO
# --------------------------------------------------------------------------- #
with abas[5]:
    st.subheader("Quais ativos andam juntos?")
    st.caption("Correlação de Pearson entre os retornos diários. Valores próximos de 1 = movimentos "
               "parecidos; próximos de 0 = pouca relação linear.")
    if len(ativos_sel) < 2:
        st.info("Selecione ao menos 2 ativos para calcular correlações.")
    else:
        ordem = (res.assign(o=res["setor"].map({s: i for i, s in enumerate(SETORES)}))
                 .sort_values(["o", "ticker"])["ticker"].tolist())
        mat = (d.pivot_table(index="data", columns="ticker", values="retorno_diario")
               [ordem].corr())
        fig = px.imshow(mat, text_auto=".2f", zmin=-1, zmax=1, aspect="auto",
                        color_continuous_scale=[[0, "#e34948"], [0.5, "#f0efec"], [1, "#2a78d6"]],
                        labels={"color": "Correlação"})
        fig.update_xaxes(side="top", title="")
        fig.update_yaxes(title="")
        st.plotly_chart(estilo(fig, 560), width="stretch")
        pares = mat.where(np.triu(np.ones(mat.shape, dtype=bool), k=1)).stack()
        alto, baixo = pares.idxmax(), pares.idxmin()
        setor_de = res.set_index("ticker")["setor"]
        mesmo = [v for (a, b), v in pares.items() if setor_de[a] == setor_de[b]]
        if mesmo:
            intra, inter = np.mean(mesmo), np.mean([v for (a, b), v in pares.items()
                                                    if setor_de[a] != setor_de[b]] or [np.nan])
            txt_setor = (f"A correlação média entre ativos do **mesmo setor** foi "
                         f"{_br(f'{intra:.2f}')}, contra {_br(f'{inter:.2f}')} entre setores diferentes"
                         + (", sinal de blocos setoriais." if intra > inter else "."))
        else:
            txt_setor = ""
        bloco_insight(
            f"O par mais correlacionado é **{alto[0]} × {alto[1]}** ({_br(f'{pares.max():.2f}')}), e o "
            f"menos correlacionado é **{baixo[0]} × {baixo[1]}** ({_br(f'{pares.min():.2f}')}). "
            + txt_setor,
            "Para diversificar, combine ativos de correlação baixa. Correlação mede apenas associação "
            "linear entre retornos e **não indica causalidade**; ela também muda ao longo do tempo.",
        )

# --------------------------------------------------------------------------- #
# 7. DADOS & EXPORTAÇÃO
# --------------------------------------------------------------------------- #
with abas[6]:
    st.subheader("Base filtrada")
    cols_exp = ["data", "ticker", "empresa", "setor", "abertura", "maxima", "minima", "fechamento",
                "fechamento_ajustado", "volume", "volume_financeiro", "retorno_diario", "base100",
                "drawdown", "sma_21", "sma_50"]
    exp = d[cols_exp].sort_values(["ticker", "data"])
    st.dataframe(exp, hide_index=True, width="stretch", height=380, column_config={
        "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
        "volume_financeiro": st.column_config.NumberColumn("Volume financeiro (R$)", format="localized"),
        "retorno_diario": st.column_config.NumberColumn("Retorno diário", format="percent"),
        "drawdown": st.column_config.NumberColumn("Drawdown", format="percent"),
    })

    def para_csv(df: pd.DataFrame) -> bytes:
        # ';' e vírgula decimal: abre corretamente no Excel em português
        return df.to_csv(index=False, sep=";", decimal=",", date_format="%d/%m/%Y").encode("utf-8-sig")

    c1, c2 = st.columns(2)
    c1.download_button("⬇️ Baixar cotações filtradas (CSV)", para_csv(exp),
                       file_name=f"cotacoes_b3_{ini:%Y%m%d}_{fim:%Y%m%d}.csv", mime="text/csv",
                       width="stretch")
    c2.download_button("⬇️ Baixar resumo por ativo (CSV)", para_csv(res),
                       file_name=f"resumo_ativos_{ini:%Y%m%d}_{fim:%Y%m%d}.csv", mime="text/csv",
                       width="stretch")
    st.caption(f"{len(exp):,} linhas · {len(ativos_sel)} ativos".replace(",", "."))

# --------------------------------------------------------------------------- #
# 8. METODOLOGIA
# --------------------------------------------------------------------------- #
with abas[7]:
    st.subheader("Metodologia, fórmulas e limitações")
    st.markdown(r"""
**Fonte:** cotações diárias da B3 obtidas pela API pública do Yahoo Finance (biblioteca `yfinance`,
sufixo `.SA`), de 01/01/2021 a 31/12/2023. Pipeline em `etl/etl_b3.py`; modelo estrela
(`dim_ativo`, `dim_data`, `fato_cotacao`) em PostgreSQL (Supabase), com CSV de contingência.

| Métrica | Fórmula |
|---|---|
| Retorno diário | $r_t = P_t / P_{t-1} - 1$ (fechamento ajustado) |
| Base 100 | $100 \times P_t / P_{0}$ |
| Retorno acumulado | $P_{fim} / P_{início} - 1$ |
| Retorno anualizado | $(1 + R_{acum})^{252/n} - 1$ |
| Volatilidade anualizada | $\sigma(r_t) \times \sqrt{252}$ |
| Sharpe | $(R_{anual} - r_f) / \sigma_{anual}$ (com $r_f = 0$ = Sharpe empírico) |
| Drawdown | $P_t / \max_{s \le t} P_s - 1$ |
| SMA *n* | média simples dos últimos *n* fechamentos ajustados |
| VaR 95% histórico | 5º percentil dos retornos diários |

**Limitações:**
- Análise **descritiva e histórica** de um recorte de 3 anos (pós-pandemia, alta da Selic e início dos cortes). Os resultados não se generalizam para outros períodos.
- Correlações e coincidências temporais **não comprovam causalidade**. Nenhum modelo econométrico foi estimado.
- O fechamento ajustado do Yahoo incorpora proventos e desdobramentos segundo a metodologia do próprio provedor; pequenas divergências em relação à B3 são possíveis.
- Volume financeiro é aproximado por *volume × fechamento* do dia.
- Não há custos de transação, impostos nem rebalanceamento na carteira simulada.
- **Nada aqui é recomendação de investimento.**
""")
