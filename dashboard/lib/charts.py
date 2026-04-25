"""
Helpers de visualização — paleta consistente e formatação PT-BR.

Centraliza paleta e layout para que todas as páginas tenham a mesma cara.
Não inclui charts complexos — a página decide a forma; aqui só ficam as
peças reutilizáveis (paleta, formatadores, layout base).
"""

from __future__ import annotations


PALETTE: dict[str, str] = {
    "primary": "#198754",   # verde — espelha .streamlit/config.toml
    "exp": "#198754",       # exportações
    "imp": "#dc3545",       # importações (vermelho discreto)
    "saldo": "#0d6efd",     # saldo (azul)
    "corrente": "#6c757d",  # corrente de comércio (cinza)
}


# Sequência categórica para charts com N séries (ex: blocos econômicos).
# Mantida sóbria — sem cores fluorescentes que machucam o olho em laptops.
CATEGORICAL_SEQUENCE: list[str] = [
    "#198754", "#dc3545", "#0d6efd", "#fd7e14",
    "#6f42c1", "#20c997", "#d63384", "#6c757d",
    "#ffc107", "#0dcaf0",
]


def fmt_usd_bi(value: float | None) -> str:
    """Formata um valor em US$ no padrão PT-BR (ex: '12,34 bi US$')."""
    if value is None:
        return "—"
    bi = value / 1e9
    # PT-BR: ponto como milhar, vírgula como decimal
    formatted = f"{bi:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} bi US$"


def fmt_usd_mi(value: float | None) -> str:
    """Formata em milhões US$ — para valores menores."""
    if value is None:
        return "—"
    mi = value / 1e6
    formatted = f"{mi:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} mi US$"


def fmt_pct(value: float | None, casas: int = 1) -> str:
    """Formata uma fração (0–1) como percentual PT-BR."""
    if value is None:
        return "—"
    return f"{value * 100:.{casas}f}%".replace(".", ",")


def base_layout(title: str | None = None, height: int = 380) -> dict:
    """Layout Plotly base — fundo branco, margens enxutas, fonte sans.

    A chave ``title`` é omitida quando ``title=None`` para evitar que o
    Plotly renderize literalmente o texto "undefined" no canto do chart
    (acontece porque ``None`` em Python vira ``undefined`` no JS).
    """
    layout: dict = {
        "font": {"family": "sans-serif", "size": 13, "color": "#212529"},
        "margin": {"l": 50, "r": 20, "t": 50 if title else 20, "b": 40},
        "plot_bgcolor": "#FFFFFF",
        "paper_bgcolor": "#FFFFFF",
        "hovermode": "x unified",
        "height": height,
        "legend": {"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
    }
    if title:
        layout["title"] = title
    return layout
