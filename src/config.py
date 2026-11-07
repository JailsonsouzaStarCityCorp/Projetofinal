"""Configurações centrais do projeto (universo de ativos, período e caminhos).

Todos os caminhos são RELATIVOS à raiz do repositório (pathlib), conforme
exigido no item 4.3 do enunciado. Nenhum caminho absoluto é usado.
"""
from pathlib import Path

# Raiz do repositório = pasta acima de /src
RAIZ = Path(__file__).resolve().parent.parent

DIR_DADOS = RAIZ / "data"
DIR_RAW = DIR_DADOS / "raw"
DIR_PROCESSED = DIR_DADOS / "processed"

CSV_FATO = DIR_PROCESSED / "fato_cotacao.csv"
CSV_DIM_ATIVO = DIR_PROCESSED / "dim_ativo.csv"
CSV_RESUMO = DIR_PROCESSED / "resumo_ativos.csv"

# Período obrigatório da Linha 2
DATA_INICIO = "2021-01-01"
DATA_FIM = "2023-12-31"  # o yfinance trata 'end' como exclusivo; o ETL soma 1 dia

DIAS_UTEIS_ANO = 252

# Universo sugerido no enunciado (12 ações líquidas).
# Setor conforme a classificação setorial da B3 (agrupada em 5 macrossetores).
# 'aliases' cobre mudanças de ticker no Yahoo Finance (ex.: Embraer EMBR3 -> EMBJ3).
ATIVOS = [
    {"ticker": "WEGE3", "empresa": "WEG", "setor": "Bens Industriais", "aliases": ["WEGE3.SA"]},
    {"ticker": "EMBR3", "empresa": "Embraer", "setor": "Bens Industriais", "aliases": ["EMBR3.SA", "EMBJ3.SA"]},
    {"ticker": "VALE3", "empresa": "Vale", "setor": "Materiais Básicos", "aliases": ["VALE3.SA"]},
    {"ticker": "GGBR4", "empresa": "Gerdau", "setor": "Materiais Básicos", "aliases": ["GGBR4.SA"]},
    {"ticker": "KLBN11", "empresa": "Klabin", "setor": "Materiais Básicos", "aliases": ["KLBN11.SA"]},
    {"ticker": "PETR4", "empresa": "Petrobras", "setor": "Petróleo e Energia", "aliases": ["PETR4.SA"]},
    {"ticker": "PRIO3", "empresa": "PRIO", "setor": "Petróleo e Energia", "aliases": ["PRIO3.SA"]},
    {"ticker": "EGIE3", "empresa": "Engie Brasil", "setor": "Petróleo e Energia", "aliases": ["EGIE3.SA"]},
    {"ticker": "ITUB4", "empresa": "Itaú Unibanco", "setor": "Financeiro", "aliases": ["ITUB4.SA"]},
    {"ticker": "BBDC4", "empresa": "Bradesco", "setor": "Financeiro", "aliases": ["BBDC4.SA"]},
    {"ticker": "ABEV3", "empresa": "Ambev", "setor": "Consumo", "aliases": ["ABEV3.SA"]},
    {"ticker": "RENT3", "empresa": "Localiza", "setor": "Consumo", "aliases": ["RENT3.SA"]},
]

SETORES = ["Bens Industriais", "Materiais Básicos", "Petróleo e Energia", "Financeiro", "Consumo"]

# Paleta categórica por SETOR (5 cores fixas, nunca recicladas).
# Cor segue a entidade (setor), nunca a posição — filtrar não repinta os demais.
CORES_SETOR = {
    "Bens Industriais": "#2a78d6",   # azul
    "Materiais Básicos": "#eb6834",  # laranja
    "Petróleo e Energia": "#1baf7a", # verde-água
    "Financeiro": "#eda100",         # amarelo
    "Consumo": "#e87ba4",            # magenta
}
SIMBOLOS_SETOR = {
    "Bens Industriais": "circle",
    "Materiais Básicos": "square",
    "Petróleo e Energia": "diamond",
    "Financeiro": "triangle-up",
    "Consumo": "x",
}
