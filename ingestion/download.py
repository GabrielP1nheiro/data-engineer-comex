"""
Comex Brasil — Download dos CSVs do MDIC / Comex Stat
======================================================
 
Script de ingestão que baixa os arquivos CSV brutos do portal do MDIC para
a pasta `data/raw/`. Na v0.1 ele é executado manualmente; a partir da v0.3
será orquestrado pelo Airflow.
 
Fonte:
    https://www.gov.br/mdic/pt-br/assuntos/comercio-exterior/estatisticas/base-de-dados-bruta
 
Padrão de URL:
    Exportação:       https://balanca.economia.gov.br/balanca/bd/comexstat-bd/ncm/EXP_{ANO}.csv
    Importação:       https://balanca.economia.gov.br/balanca/bd/comexstat-bd/ncm/IMP_{ANO}.csv
    Tabelas auxiliares: https://balanca.economia.gov.br/balanca/bd/tabelas/{NOME}.csv
 
Uso:
    python ingestion/download.py                          # baixa EXP+IMP de 2020–2024 + auxiliares
    python ingestion/download.py --anos 2023 2024         # baixa apenas 2023 e 2024
    python ingestion/download.py --direcao exp            # baixa apenas exportações
    python ingestion/download.py --sem-aux                # não baixa tabelas auxiliares
    python ingestion/download.py --force                  # re-baixa mesmo se já existir
"""
 
from __future__ import annotations

import argparse
import logging
import sys
from enum import Enum
from pathlib import Path

import requests
import urllib3


class Result(Enum):
    """Resultado de uma operação de download individual."""
    OK = "ok"
    SKIPPED = "skipped"
    FAILED = "failed"
 
# -----------------------------------------------------------------------------
# Configuração SSL
# -----------------------------------------------------------------------------
# O servidor do MDIC (balanca.economia.gov.br) usa certificado emitido pela
# ICP-Brasil, que não está na lista de CAs confiáveis da imagem Docker do
# Airflow. Como os dados são públicos e o host é um domínio .gov.br conhecido,
# desabilitamos a verificação SSL. Em produção cloud (v1.1+), o BigQuery e o
# Cloud Storage resolvem isso de outra forma.
VERIFY_SSL = False
 
# Silencia o warning "InsecureRequestWarning" do urllib3 quando VERIFY_SSL=False
if not VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
 
# -----------------------------------------------------------------------------
# Configuração
# -----------------------------------------------------------------------------
 
BASE_URL_NCM = "https://balanca.economia.gov.br/balanca/bd/comexstat-bd/ncm"
BASE_URL_AUX = "https://balanca.economia.gov.br/balanca/bd/tabelas"
 
# Anos padrão do projeto (v0.1: foco em 2020–2024)
ANOS_PADRAO = [2020, 2021, 2022, 2023, 2024]
 
# Tabelas auxiliares essenciais para o projeto
TABELAS_AUXILIARES = [
    "NCM",              # produtos (Nomenclatura Comum do Mercosul)
    "NCM_SH",           # hierarquia do Sistema Harmonizado
    "PAIS",             # códigos de países
    "PAIS_BLOCO",       # blocos econômicos (Mercosul, UE, Ásia...)
    "UF",               # estados brasileiros
    "VIA",              # vias de transporte
    "URF",              # Unidades da Receita Federal
]
 
# Localização das pastas do projeto (relativa ao diretório raiz)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_EXP = DATA_DIR / "raw" / "exp"
RAW_IMP = DATA_DIR / "raw" / "imp"
AUX_DIR = DATA_DIR / "aux"
 
# Tamanho do bloco em streaming (8 MB — bom equilíbrio para arquivos grandes)
CHUNK_SIZE = 8 * 1024 * 1024
 
# Timeout generoso: os servidores do MDIC podem ser lentos
REQUEST_TIMEOUT = 60
 
# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("comex.download")
 
 
# -----------------------------------------------------------------------------
# Funções de download
# -----------------------------------------------------------------------------
 
def _download_streaming(url: str, destino: Path, force: bool = False) -> Result:
    """
    Baixa um arquivo via HTTP em streaming, escrevendo em blocos no disco.

    Streaming evita carregar o arquivo inteiro na memória — essencial porque
    os CSVs do MDIC podem passar de 1 GB.
    """
    if destino.exists() and not force:
        tamanho_mb = destino.stat().st_size / (1024 * 1024)
        log.info(f"⏭  Pulando (já existe): {destino.name} [{tamanho_mb:.1f} MB]")
        return Result.SKIPPED

    destino.parent.mkdir(parents=True, exist_ok=True)

    log.info(f"⬇  Baixando: {url}")
    try:
        with requests.get(
            url,
            stream=True,
            timeout=REQUEST_TIMEOUT,
            verify=VERIFY_SSL,
        ) as resposta:
            resposta.raise_for_status()

            tamanho_total = int(resposta.headers.get("Content-Length", 0))
            tamanho_total_mb = tamanho_total / (1024 * 1024) if tamanho_total else 0

            baixado = 0
            with open(destino, "wb") as arquivo:
                for bloco in resposta.iter_content(chunk_size=CHUNK_SIZE):
                    if not bloco:
                        continue
                    arquivo.write(bloco)
                    baixado += len(bloco)

                    # Progresso apenas se soubermos o tamanho total
                    if tamanho_total:
                        pct = (baixado / tamanho_total) * 100
                        baixado_mb = baixado / (1024 * 1024)
                        print(
                            f"   {baixado_mb:>7.1f} / {tamanho_total_mb:>7.1f} MB "
                            f"({pct:>5.1f}%)",
                            end="\r",
                            flush=True,
                        )
            print()  # quebra de linha após o progresso

    except requests.HTTPError as e:
        log.error(f"❌ Erro HTTP {e.response.status_code} em {url}")
        if destino.exists():
            destino.unlink()
        return Result.FAILED
    except requests.RequestException as e:
        log.error(f"❌ Falha de rede em {url}: {e}")
        if destino.exists():
            destino.unlink()
        return Result.FAILED

    tamanho_mb = destino.stat().st_size / (1024 * 1024)
    log.info(f"✅ Salvo: {destino.name} [{tamanho_mb:.1f} MB]")
    return Result.OK
 
 
def baixar_ncm(ano: int, direcao: str, force: bool = False) -> Result:
    """
    Baixa um arquivo NCM (EXP ou IMP) de um ano específico.

    Args:
        ano: ano do arquivo (ex: 2024)
        direcao: 'exp' para exportação, 'imp' para importação
        force: se True, re-baixa mesmo que o arquivo já exista
    """
    direcao_upper = direcao.upper()
    if direcao_upper not in ("EXP", "IMP"):
        raise ValueError(f"Direção inválida: {direcao}. Use 'exp' ou 'imp'.")

    nome_arquivo = f"{direcao_upper}_{ano}.csv"
    url = f"{BASE_URL_NCM}/{nome_arquivo}"
    pasta = RAW_EXP if direcao_upper == "EXP" else RAW_IMP
    destino = pasta / nome_arquivo

    return _download_streaming(url, destino, force=force)


def baixar_tabela_auxiliar(nome: str, force: bool = False) -> Result:
    """
    Baixa uma tabela auxiliar (NCM, PAIS, UF, etc.) do MDIC.
    """
    nome_arquivo = f"{nome}.csv"
    url = f"{BASE_URL_AUX}/{nome_arquivo}"
    destino = AUX_DIR / nome_arquivo

    return _download_streaming(url, destino, force=force)
 
 
# -----------------------------------------------------------------------------
# Orquestração
# -----------------------------------------------------------------------------
 
def executar(
    anos: list[int],
    direcoes: list[str],
    baixar_aux: bool = True,
    force: bool = False,
) -> int:
    """
    Executa o download completo conforme os parâmetros fornecidos.

    Retorna o número de falhas. Zero significa que tudo correu bem
    (arquivos baixados ou pulados por já existirem).
    """
    log.info("=" * 60)
    log.info("COMEX BRASIL — Download de dados do MDIC")
    log.info("=" * 60)
    log.info(f"Anos:       {anos}")
    log.info(f"Direções:   {direcoes}")
    log.info(f"Auxiliares: {'sim' if baixar_aux else 'não'}")
    log.info(f"Force:      {'sim' if force else 'não'}")
    log.info("=" * 60)

    baixados = 0
    pulados = 0
    falhas: list[str] = []

    def _registrar(resultado: Result, rotulo: str) -> None:
        nonlocal baixados, pulados
        if resultado is Result.OK:
            baixados += 1
        elif resultado is Result.SKIPPED:
            pulados += 1
        else:
            falhas.append(rotulo)

    # Dados NCM (exportação/importação)
    for direcao in direcoes:
        for ano in anos:
            _registrar(
                baixar_ncm(ano, direcao, force=force),
                f"{direcao.upper()}_{ano}.csv",
            )

    # Tabelas auxiliares
    if baixar_aux:
        log.info("-" * 60)
        log.info("Tabelas auxiliares")
        log.info("-" * 60)
        for nome in TABELAS_AUXILIARES:
            _registrar(
                baixar_tabela_auxiliar(nome, force=force),
                f"{nome}.csv",
            )

    log.info("=" * 60)
    log.info(
        f"Concluído: {baixados} baixados, {pulados} pulados, {len(falhas)} falhas"
    )
    if falhas:
        log.error(f"❌ Arquivos com falha: {', '.join(falhas)}")
    log.info("=" * 60)

    return len(falhas)
 
 
def parse_args() -> argparse.Namespace:
    """Parser dos argumentos de linha de comando."""
    parser = argparse.ArgumentParser(
        description="Baixa os CSVs do MDIC / Comex Stat.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--anos",
        type=int,
        nargs="+",
        default=ANOS_PADRAO,
        help="Anos a baixar (separados por espaço).",
    )
    parser.add_argument(
        "--direcao",
        choices=["exp", "imp", "ambos"],
        default="ambos",
        help="Qual direção baixar: exportação, importação ou ambas.",
    )
    parser.add_argument(
        "--sem-aux",
        action="store_true",
        help="Não baixa as tabelas auxiliares (NCM, PAIS, UF, etc.).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-baixa arquivos mesmo que já existam localmente.",
    )
    return parser.parse_args()
 
 
def main() -> int:
    args = parse_args()
 
    # Resolve direções
    if args.direcao == "ambos":
        direcoes = ["exp", "imp"]
    else:
        direcoes = [args.direcao]
 
    try:
        falhas = executar(
            anos=args.anos,
            direcoes=direcoes,
            baixar_aux=not args.sem_aux,
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
 