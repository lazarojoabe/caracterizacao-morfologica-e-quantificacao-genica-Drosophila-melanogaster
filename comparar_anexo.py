"""Compara os CSVs de resultados anexados com o pipeline do projeto.

O ZIP contém três conjuntos experimentais. Este script seleciona apenas o
conjunto ``Larvas_desafiadas_04_04_2014``, que corresponde às imagens presentes
em ``imagens_nucleos`` e ``imagens_proteinas``.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import zipfile
from pathlib import Path

import cv2
import numpy as np


DATASET_MARKER = "results_set20220613_Larvas_desafiadas_04_04_2014/"


def to_float(value: str) -> float:
    return float(value.strip().replace(",", "."))


def external_key(member_name: str) -> str:
    name = Path(member_name).name
    name = re.sub(r"_data\.csv$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"(?:_z0)?_ch02$", "", name, flags=re.IGNORECASE)
    return name


def safe_name(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.+-]", "_", key)


def mask_metrics(
    archive: zipfile.ZipFile, csv_member: str, key: str, algorithm_mask_dir: Path
) -> dict[str, float | int]:
    mask_member = re.sub(
        r"_ch02_data\.csv$", "_ch00_mask.png", csv_member, flags=re.IGNORECASE
    )
    external_mask = cv2.imdecode(
        np.frombuffer(archive.read(mask_member), dtype=np.uint8), cv2.IMREAD_GRAYSCALE
    )
    algorithm_mask = cv2.imread(
        str(algorithm_mask_dir / f"{safe_name(key)}.png"), cv2.IMREAD_GRAYSCALE
    )
    if external_mask is None or algorithm_mask is None:
        return {}
    if external_mask.shape != algorithm_mask.shape:
        return {
            "external_mask_foreground_px": int(np.count_nonzero(external_mask)),
            "algorithm_mask_foreground_px": int(np.count_nonzero(algorithm_mask)),
        }
    external_binary = external_mask > 0
    algorithm_binary = algorithm_mask > 0
    intersection = int(np.count_nonzero(external_binary & algorithm_binary))
    union = int(np.count_nonzero(external_binary | algorithm_binary))
    external_count = int(np.count_nonzero(external_binary))
    algorithm_count = int(np.count_nonzero(algorithm_binary))
    return {
        "external_mask_foreground_px": external_count,
        "algorithm_mask_foreground_px": algorithm_count,
        "mask_intersection_px": intersection,
        "mask_union_px": union,
        "mask_iou": intersection / union if union else math.nan,
        "mask_dice": 2 * intersection / (external_count + algorithm_count)
        if external_count + algorithm_count
        else math.nan,
    }


def read_external(zip_path: Path, algorithm_mask_dir: Path) -> dict[str, dict]:
    result: dict[str, dict] = {}
    with zipfile.ZipFile(zip_path) as archive:
        members = [
            name
            for name in archive.namelist()
            if name.startswith(DATASET_MARKER)
            and name.lower().endswith("_ch02_data.csv")
        ]
        for member in sorted(members):
            key = external_key(member)
            with archive.open(member) as stream:
                text = stream.read().decode("utf-8-sig")
            rows = list(csv.DictReader(text.splitlines()))
            intensities = np.array(
                [to_float(row["intensidade"]) for row in rows], dtype=float
            )
            areas = np.array(
                [to_float(row["area"]) for row in rows], dtype=float
            )
            result[key] = {
                "external_file": Path(member).name,
                "external_nucleus_count": int(len(rows)),
                "external_mean_intensity": float(intensities.mean())
                if intensities.size
                else math.nan,
                "external_median_intensity": float(np.median(intensities))
                if intensities.size
                else math.nan,
                "external_mean_area_px": float(areas.mean()) if areas.size else math.nan,
                "external_total_area_px": float(areas.sum()) if areas.size else math.nan,
            }
            result[key].update(mask_metrics(archive, member, key, algorithm_mask_dir))
    return result


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def read_algorithm(output_dir: Path) -> dict[str, dict]:
    summaries = {
        row["sample_key"]: row
        for row in read_csv_rows(output_dir / "resumo_por_amostra.csv")
    }
    nuclei: dict[str, list[dict[str, str]]] = {}
    for row in read_csv_rows(output_dir / "resultados_por_nucleo.csv"):
        nuclei.setdefault(row["sample_key"], []).append(row)

    result: dict[str, dict] = {}
    for key, summary in summaries.items():
        rows = nuclei.get(key, [])
        areas = np.array([to_float(row["area_px"]) for row in rows], dtype=float)
        result[key] = {
            "algorithm_status": summary.get("status", ""),
            "algorithm_nucleus_count": int(summary.get("nucleus_count", 0)),
            "algorithm_mean_raw_intensity": to_float(
                summary.get("mean_raw_red_per_nucleus", "nan")
            ),
            "algorithm_mean_area_px": float(areas.mean()) if areas.size else math.nan,
            "algorithm_total_area_px": float(areas.sum()) if areas.size else math.nan,
        }
    return result


def difference(value: float, reference: float) -> tuple[float, float]:
    if not np.isfinite(value) or not np.isfinite(reference):
        return math.nan, math.nan
    delta = value - reference
    relative = delta / reference * 100 if reference != 0 else math.nan
    return delta, relative


def make_rows(external: dict[str, dict], algorithm: dict[str, dict]) -> list[dict]:
    rows: list[dict] = []
    for key in sorted(set(external) | set(algorithm)):
        row = {"sample_key": key}
        row.update(external.get(key, {}))
        row.update(algorithm.get(key, {}))
        ext = row.get("external_mean_intensity", math.nan)
        raw = row.get("algorithm_mean_raw_intensity", math.nan)
        raw_delta, raw_relative = difference(raw, ext)
        row.update(
            {
                "delta_raw_minus_external": raw_delta,
                "relative_raw_vs_external_percent": raw_relative,
                "delta_nucleus_count": (
                    row.get("algorithm_nucleus_count", math.nan)
                    - row.get("external_nucleus_count", math.nan)
                ),
                "delta_total_area_px": (
                    row.get("algorithm_total_area_px", math.nan)
                    - row.get("external_total_area_px", math.nan)
                ),
                "delta_mask_foreground_px": (
                    row.get("algorithm_mask_foreground_px", math.nan)
                    - row.get("external_mask_foreground_px", math.nan)
                ),
                "raw_within_10_percent": (
                    bool(abs(raw_relative) <= 10) if np.isfinite(raw_relative) else False
                ),
            }
        )
        rows.append(row)
    return rows


def finite_values(rows: list[dict], field: str) -> np.ndarray:
    return np.array(
        [float(row[field]) for row in rows if np.isfinite(float(row.get(field, math.nan)))],
        dtype=float,
    )


def rank_values(values: np.ndarray) -> np.ndarray:
    return np.argsort(np.argsort(values)).astype(float)


def summary(rows: list[dict]) -> dict:
    common = [
        row
        for row in rows
        if row.get("external_nucleus_count") is not None
        and row.get("algorithm_status") == "ok"
    ]
    external = finite_values(common, "external_mean_intensity")
    raw = finite_values(common, "algorithm_mean_raw_intensity")
    raw_delta = finite_values(common, "delta_raw_minus_external")
    raw_relative = finite_values(common, "relative_raw_vs_external_percent")
    mask_iou = finite_values(common, "mask_iou")
    mask_dice = finite_values(common, "mask_dice")
    paired = min(len(external), len(raw))

    def mean_abs(values: np.ndarray) -> float | None:
        return float(np.mean(np.abs(values))) if values.size else None

    def median_abs(values: np.ndarray) -> float | None:
        return float(np.median(np.abs(values))) if values.size else None

    result = {
        "external_dataset_csv_count": len(rows),
        "common_images_compared": len(common),
        "missing_in_external": sum("external_nucleus_count" not in row for row in rows),
        "missing_in_algorithm": sum("algorithm_status" not in row for row in rows),
        "external_mean_of_image_means": float(external.mean()) if external.size else None,
        "algorithm_raw_mean_of_image_means": float(raw.mean()) if raw.size else None,
        "mean_bias_raw_minus_external": float(raw_delta.mean()) if raw_delta.size else None,
        "mae_raw_vs_external": mean_abs(raw_delta),
        "median_absolute_error_raw_vs_external": median_abs(raw_delta),
        "mean_absolute_relative_error_raw_percent": mean_abs(raw_relative),
        "raw_images_within_10_percent": sum(
            bool(row["raw_within_10_percent"]) for row in common
        ),
        "mean_external_nucleus_count": float(
            np.mean([row["external_nucleus_count"] for row in common])
        )
        if common
        else None,
        "mean_algorithm_nucleus_count": float(
            np.mean([row["algorithm_nucleus_count"] for row in common])
        )
        if common
        else None,
        "mean_mask_iou": float(mask_iou.mean()) if mask_iou.size else None,
        "mean_mask_dice": float(mask_dice.mean()) if mask_dice.size else None,
    }
    if paired and external.size == raw.size:
        result["pearson_correlation_raw_vs_external"] = float(
            np.corrcoef(external, raw)[0, 1]
        )
        result["spearman_correlation_raw_vs_external"] = float(
            np.corrcoef(rank_values(external), rank_values(raw))[0, 1]
        )
    else:
        result.update(
            {
                "pearson_correlation_raw_vs_external": None,
                "spearman_correlation_raw_vs_external": None,
            }
        )
    return result


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: object, digits: int = 3) -> str:
    if value is None or value == "":
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return "—" if not math.isfinite(number) else f"{number:.{digits}f}"


def write_markdown(path: Path, rows: list[dict], report: dict, zip_path: Path) -> None:
    lines = [
        "# Comparação com os resultados anexados",
        "",
        f"Arquivo analisado: `{zip_path}`.",
        "",
        "Foram usados somente os 43 CSVs do conjunto `Larvas desafiadas_04_04_2014`, que correspondem às 43 imagens do projeto. Os demais 161 CSVs do ZIP pertencem a outros conjuntos experimentais.",
        "",
        "A métrica principal do anexo é a média de `intensidade` por núcleo. A comparação direta usa a média de intensidade do canal vermelho dentro dos núcleos (`algorithm_mean_raw_intensity`).",
        "",
        "## Resumo",
        "",
        f"- Imagens comparadas: **{report['common_images_compared']}**.",
        f"- Média das médias do anexo: **{fmt(report['external_mean_of_image_means'])}**.",
        f"- Média das médias do algoritmo: **{fmt(report['algorithm_raw_mean_of_image_means'])}**.",
        f"- Erro absoluto médio: **{fmt(report['mae_raw_vs_external'])}** (**{fmt(report['mean_absolute_relative_error_raw_percent'])}%** relativo).",
        f"- Imagens dentro de ±10%: **{report['raw_images_within_10_percent']}**.",
        f"- Correlação de Pearson: **{fmt(report['pearson_correlation_raw_vs_external'])}**.",
        f"- Concordância média das máscaras: **IoU {fmt(report['mean_mask_iou'])}** e **Dice {fmt(report['mean_mask_dice'])}**.",
        "",
        "## Comparação por imagem",
        "",
        "| Imagem | N anexo | N algoritmo | Média anexo | Média do algoritmo | Δ | Δ % | Área anexo | Área algoritmo | IoU máscara | Dice máscara |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {key} | {en} | {an} | {em} | {ar} | {d} | {dp}% | {ea} | {aa} | {iou} | {dice} |".format(
                key=row["sample_key"],
                en=fmt(row.get("external_nucleus_count"), 0),
                an=fmt(row.get("algorithm_nucleus_count"), 0),
                em=fmt(row.get("external_mean_intensity")),
                ar=fmt(row.get("algorithm_mean_raw_intensity")),
                d=fmt(row.get("delta_raw_minus_external")),
                dp=fmt(row.get("relative_raw_vs_external_percent")),
                ea=fmt(row.get("external_total_area_px"), 0),
                aa=fmt(row.get("algorithm_total_area_px"), 0),
                iou=fmt(row.get("mask_iou")),
                dice=fmt(row.get("mask_dice")),
            )
        )
    lines.extend(
        [
            "",
            "O CSV correspondente contém também medianas, médias de área e indicadores de tolerância para auditoria numérica.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_simple_comparison_table(output_dir: Path, rows: list[dict]) -> None:
    """Exporta somente as três colunas solicitadas para comparação rápida."""

    table_rows = [
        {
            "nome_da_imagem": row["sample_key"],
            "media_de_proteina_anexo": row.get("external_mean_intensity", math.nan),
            "media_de_proteina_meu_algoritmo": row.get(
                "algorithm_mean_raw_intensity", math.nan
            ),
        }
        for row in rows
    ]
    csv_path = output_dir / "tabela_comparacao_media_proteina.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(table_rows[0].keys()))
        writer.writeheader()
        writer.writerows(table_rows)

    markdown_lines = [
        "# Tabela comparativa da média de proteína",
        "",
        "| Nome da imagem | Média de proteína — algoritmo do ZIP | Média de proteína — meu algoritmo |",
        "|---|---:|---:|",
    ]
    for row in table_rows:
        markdown_lines.append(
            f"| {row['nome_da_imagem']} | "
            f"{fmt(row['media_de_proteina_anexo'])} | "
            f"{fmt(row['media_de_proteina_meu_algoritmo'])} |"
        )
    (output_dir / "tabela_comparacao_media_proteina.md").write_text(
        "\n".join(markdown_lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--zip",
        dest="zip_path",
        type=Path,
        default=Path.home() / "Downloads" / "results13062022.zip",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("resultados_tcc"))
    args = parser.parse_args()

    external = read_external(
        args.zip_path, args.output_dir / "mascaras_melhoradas"
    )
    algorithm = read_algorithm(args.output_dir)
    rows = make_rows(external, algorithm)
    report = summary(rows)
    report["zip_path"] = str(args.zip_path)
    output_dir = args.output_dir
    write_csv(output_dir / "comparacao_anexo_por_imagem.csv", rows)
    (output_dir / "comparacao_anexo_resumo.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_markdown(
        output_dir / "comparacao_anexo_resultados.md", rows, report, args.zip_path
    )
    write_simple_comparison_table(output_dir, rows)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
