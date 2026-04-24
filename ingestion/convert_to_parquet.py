"""
Comex Brasil — Conversão CSV → Parquet
=======================================

Converte os CSVs brutos do MDIC (pasta `data/raw/`) para arquivos Parquet
comprimidos (pasta `data/parquet/`). Usa Polars para performance em
arquivos grandes.

Por que Parquet?
    • Comprimido (tipicamente 5-10x menor que CSV)
    • Colunar: queries em colunas específicas são muito mais rápidas
    • Preserva tipos de dados (não precisa re-inferir a cada leitura)
    • DuckDB lê Parquet nativamente, sem precisar carregar em banco

Notas técnicas sobre os arquivos do MDIC:
    • Encoding: Latin-1 (ISO-8859-1), NÃO UTF-8
    • Separador: ponto e vírgula (;)
    • Campos vêm entre aspas duplas
    • Códigos (CO_*, SG_*) têm zeros à esquerda — tratar como STRING
    • Apenas QT_ESTAT, KG_LIQUIDO, VL_FOB e VL_FRETE/VL_SEGURO (IMP) são numéricos

Uso:
    python ingestion/convert_to_parquet.py                      # converte tudo
    python ingestion/convert_to_parquet.py --direcao exp        # só exportação
    python ingestion/convert_to_parquet.py --sem-aux            # pula tabelas auxiliares
    python ingestion/convert_to_parquet.py --force              # reprocessa mesmo se já existir
"""

from __future__ import annotations

import argparse
import logging
import sys
from enum import Enum
from pathlib import Path

import polars as pl


class Result(Enum):
    """Resultado de uma conversão individual."""
    OK = "ok"
    SKIPPED = "skipped"
    FAILED = "failed"

# -----------------------------------------------------------------------------
# Configuração
# -----------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

RAW_EXP = DATA_DIR / "raw" / "exp"
RAW_IMP = DATA_DIR / "raw" / "imp"
AUX_DIR = DATA_DIR / "aux"

PARQUET_EXP = DATA_DIR / "parquet" / "exp"
PARQUET_IMP = DATA_DIR / "parquet" / "imp"
PARQUET_AUX = DATA_DIR / "parquet" / "aux"

ENCODING = "latin-1"
SEPARADOR = ";"

# Schemas explícitos: tudo string por padrão, exceto métricas numéricas
# Isso evita que Polars infira tipos errados em códigos com zero à esquerda

SCHEMA_EXP = {
    "CO_ANO": pl.String,
    "CO_MES": pl.String,
    "CO_NCM": pl.String,
    "CO_UNID": pl.String,
    "CO_PAIS": pl.String,
    "SG_UF_NCM": pl.String,
    "CO_VIA": pl.String,
    "CO_URF": pl.String,
    "QT_ESTAT": pl.Int64,
    "KG_LIQUIDO": pl.Int64,
    "VL_FOB": pl.Int64,
}

SCHEMA_IMP = {
    **SCHEMA_EXP,
    "VL_FRETE": pl.Int64,
    "VL_SEGURO": pl.Int64,
}

# Compressão: zstd oferece melhor razão compressão/velocidade para Parquet
COMPRESSAO = "zstd"

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("comex.convert")


# -----------------------------------------------------------------------------
# Funções de conversão
# -----------------------------------------------------------------------------

def _converter_csv(
    origem: Path,
    destino: Path,
    schema: dict | None = None,
    force: bool = False,
) -> Result:
    """
    Converte um arquivo CSV em Parquet.

    Args:
        origem: caminho do CSV
        destino: caminho de saída do Parquet
        schema: se fornecido, força os tipos das colunas (evita inferência errada)
        force: se True, reprocessa mesmo que o destino já exista
    """
    if not origem.exists():
        # Origem ausente é falha: quem chamou esperava encontrar o arquivo.
        log.error(f"❌ Origem não encontrada: {origem}")
        return Result.FAILED

    if destino.exists() and not force:
        tamanho_mb = destino.stat().st_size / (1024 * 1024)
        log.info(f"⏭  Pulando (já existe): {destino.name} [{tamanho_mb:.1f} MB]")
        return Result.SKIPPED

    destino.parent.mkdir(parents=True, exist_ok=True)

    tamanho_csv_mb = origem.stat().st_size / (1024 * 1024)
    log.info(f"🔄 Convertendo: {origem.name} [{tamanho_csv_mb:.1f} MB]")

    try:
        if schema:
            df = pl.read_csv(
                origem,
                separator=SEPARADOR,
                encoding=ENCODING,
                schema_overrides=schema,
            )
        else:
            # Tabelas auxiliares: inferência automática é segura (arquivos pequenos)
            df = pl.read_csv(
                origem,
                separator=SEPARADOR,
                encoding=ENCODING,
                infer_schema_length=10_000,
            )

        num_linhas = df.height
        num_colunas = df.width

        df.write_parquet(destino, compression=COMPRESSAO)

    except Exception as e:
        log.error(f"❌ Erro ao converter {origem.name}: {e}")
        if destino.exists():
            destino.unlink()
        return Result.FAILED

    tamanho_pq_mb = destino.stat().st_size / (1024 * 1024)
    razao = tamanho_csv_mb / tamanho_pq_mb if tamanho_pq_mb > 0 else 0
    log.info(
        f"✅ Salvo: {destino.name} [{tamanho_pq_mb:.1f} MB, "
        f"{num_linhas:,} linhas × {num_colunas} colunas, "
        f"compressão {razao:.1f}x]"
    )
    return Result.OK


def converter_ncm(direcao: str, force: bool = False) -> tuple[int, int, list[str]]:
    """
    Converte todos os arquivos NCM de uma direção (exp ou imp).
    Retorna (convertidos, pulados, falhas) onde falhas é a lista de nomes
    de arquivo que falharam.
    """
    direcao_upper = direcao.upper()
    if direcao_upper == "EXP":
        pasta_origem = RAW_EXP
        pasta_destino = PARQUET_EXP
        schema = SCHEMA_EXP
    elif direcao_upper == "IMP":
        pasta_origem = RAW_IMP
        pasta_destino = PARQUET_IMP
        schema = SCHEMA_IMP
    else:
        raise ValueError(f"Direção inválida: {direcao}")

    convertidos = 0
    pulados = 0
    falhas: list[str] = []

    arquivos = sorted(pasta_origem.glob(f"{direcao_upper}_*.csv"))

    if not arquivos:
        # Sem arquivos não é falha aqui: pode ser intencional (p.ex. rodar só
        # `--direcao exp` sem ter baixado imp). Quem chama decide se faz falta.
        log.warning(f"⚠  Nenhum CSV encontrado em {pasta_origem}")
        return 0, 0, falhas

    for csv_path in arquivos:
        parquet_path = pasta_destino / csv_path.name.replace(".csv", ".parquet")
        resultado = _converter_csv(csv_path, parquet_path, schema=schema, force=force)
        if resultado is Result.OK:
            convertidos += 1
        elif resultado is Result.SKIPPED:
            pulados += 1
        else:
            falhas.append(csv_path.name)

    return convertidos, pulados, falhas


def converter_auxiliares(force: bool = False) -> tuple[int, int, list[str]]:
    """
    Converte todas as tabelas auxiliares.
    Retorna (convertidos, pulados, falhas).
    """
    convertidos = 0
    pulados = 0
    falhas: list[str] = []

    arquivos = sorted(AUX_DIR.glob("*.csv"))

    if not arquivos:
        log.warning(f"⚠  Nenhuma tabela auxiliar encontrada em {AUX_DIR}")
        return 0, 0, falhas

    for csv_path in arquivos:
        parquet_path = PARQUET_AUX / csv_path.name.replace(".csv", ".parquet")
        resultado = _converter_csv(csv_path, parquet_path, schema=None, force=force)
        if resultado is Result.OK:
            convertidos += 1
        elif resultado is Result.SKIPPED:
            pulados += 1
        else:
            falhas.append(csv_path.name)

    return convertidos, pulados, falhas


# -----------------------------------------------------------------------------
# Orquestração
# -----------------------------------------------------------------------------

def executar(
    direcoes: list[str],
    converter_aux: bool = True,
    force: bool = False,
) -> int:
    """
    Executa a conversão completa conforme os parâmetros fornecidos.

    Retorna o número de falhas. Zero significa que tudo foi convertido
    ou pulado por já existir.
    """
    log.info("=" * 60)
    log.info("COMEX BRASIL — Conversão CSV → Parquet")
    log.info("=" * 60)
    log.info(f"Direções:   {direcoes}")
    log.info(f"Auxiliares: {'sim' if converter_aux else 'não'}")
    log.info(f"Force:      {'sim' if force else 'não'}")
    log.info("=" * 60)

    total_conv = 0
    total_pul = 0
    total_falhas: list[str] = []

    # Dados NCM
    for direcao in direcoes:
        log.info(f"--- {direcao.upper()} ---")
        conv, pul, falhas = converter_ncm(direcao, force=force)
        total_conv += conv
        total_pul += pul
        total_falhas.extend(falhas)

    # Tabelas auxiliares
    if converter_aux:
        log.info("--- AUXILIARES ---")
        conv, pul, falhas = converter_auxiliares(force=force)
        total_conv += conv
        total_pul += pul
        total_falhas.extend(falhas)

    log.info("=" * 60)
    log.info(
        f"Concluído: {total_conv} convertidos, {total_pul} pulados, "
        f"{len(total_falhas)} falhas"
    )
    if total_falhas:
        log.error(f"❌ Arquivos com falha: {', '.join(total_falhas)}")
    log.info("=" * 60)

    return len(total_falhas)


def parse_args() -> argparse.Namespace:
    """Parser dos argumentos de linha de comando."""
    parser = argparse.ArgumentParser(
        description="Converte os CSVs do MDIC em Parquet.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--direcao",
        choices=["exp", "imp", "ambos"],
        default="ambos",
        help="Qual direção converter.",
    )
    parser.add_argument(
        "--sem-aux",
        action="store_true",
        help="Não converte as tabelas auxiliares.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocessa arquivos mesmo que o Parquet já exista.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.direcao == "ambos":
        direcoes = ["exp", "imp"]
    else:
        direcoes = [args.direcao]

    try:
        falhas = executar(
            direcoes=direcoes,
            converter_aux=not args.sem_aux,
            force=args.force,
        )
    except KeyboardInterrupt:
        log.warning("\n⚠  Interrompido pelo usuário.")
        return 130
    except Exception as e:
        log.exception(f"Erro inesperado: {e}")
        return 1

    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
