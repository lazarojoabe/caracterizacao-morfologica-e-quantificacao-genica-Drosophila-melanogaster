"""Compara as medidas do Breno com o pipeline revisado no results13062022.

A pasta ``results13062022`` contém resultados derivados, não os TIFFs brutos.
Por isso este adaptador usa, para cada CSV do Breno, a máscara ``ch00_mask``
e a imagem ``ch02_border`` correspondente. A máscara passa novamente pela
segmentação de ``pipeline_melhorado``; na imagem de proteína, os pixels brancos
do contorno desenhado são ignorados antes da quantificação.

O resultado deve ser interpretado como uma comparação de compatibilidade com
os PNGs exportados, e não como uma execução nos TIFFs originais.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path

import cv2
import numpy as np

from pipeline_melhorado import PipelineConfig, segment_nuclei


DATA_SUFFIX = re.compile(r"_ch02_data\.csv$", re.IGNORECASE)


def to_float(value: str) -> float:
    return float(value.strip().replace(",", "."))


def image_key(csv_path: Path) -> str:
    return DATA_SUFFIX.sub("", csv_path.name)


def read_png(path: Path, mode: int) -> np.ndarray:
    """Lê PNG por bytes para funcionar mesmo com acentos no caminho."""

    image = cv2.imdecode(np.frombuffer(path.read_bytes(), dtype=np.uint8), mode)
    if image is None:
        raise IOError(f"Não foi possível ler a imagem: {path}")
    return image


def breno_measurement(csv_path: Path) -> tuple[float, int]:
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    intensities = np.array(
        [to_float(row["intensidade"]) for row in rows], dtype=float
    )
    return (
        float(intensities.mean()) if intensities.size else math.nan,
        int(intensities.size),
    )


def measure_with_pipeline(mask_path: Path, protein_path: Path, config: PipelineConfig) -> tuple[float, int]:
    nucleus_mask = read_png(mask_path, cv2.IMREAD_GRAYSCALE)
    protein_image = read_png(protein_path, cv2.IMREAD_UNCHANGED)
    if protein_image.ndim == 2:
        protein = protein_image.astype(np.float32)
    elif protein_image.ndim == 3 and protein_image.shape[2] >= 3:
        # OpenCV armazena PNG BGR; o canal vermelho é o índice 2.
        protein = protein_image[:, :, 2].astype(np.float32)
    else:
        raise ValueError(f"Formato de proteína incompatível: {protein_path}")
    if nucleus_mask.shape != protein.shape:
        raise ValueError(
            f"Dimensões incompatíveis: {mask_path.name} {nucleus_mask.shape} vs "
            f"{protein_path.name} {protein.shape}"
        )

    labels, _, _ = segment_nuclei(nucleus_mask.astype(np.float32), config)
    flat_labels = labels.ravel()
    max_label = int(labels.max())
    if max_label == 0:
        return math.nan, 0

    # O arquivo ch02_border já contém linhas brancas de controle visual.
    # Removê-las evita contar o valor 255 como intensidade biológica.
    if protein_image.ndim == 3:
        flat_rgb = protein_image.reshape(-1, protein_image.shape[2])
        valid_pixels = np.any(flat_rgb < 250, axis=1)
    else:
        valid_pixels = np.ones(flat_labels.shape, dtype=bool)

    labels_valid = flat_labels[valid_pixels]
    protein_valid = protein.ravel()[valid_pixels]
    counts = np.bincount(labels_valid, minlength=max_label + 1)
    sums = np.bincount(
        labels_valid, weights=protein_valid, minlength=max_label + 1
    )
    nucleus_means = sums[1:] / counts[1:]
    nucleus_means = nucleus_means[counts[1:] > 0]
    return (
        float(nucleus_means.mean()) if nucleus_means.size else math.nan,
        int(nucleus_means.size),
    )


def difference(value: float, reference: float) -> tuple[float, float]:
    if not np.isfinite(value) or not np.isfinite(reference):
        return math.nan, math.nan
    delta = value - reference
    relative = delta / reference * 100 if reference != 0 else math.nan
    return delta, relative


def finite_mean(values: list[float]) -> float | None:
    finite = np.asarray([value for value in values if np.isfinite(value)])
    return float(finite.mean()) if finite.size else None


def run(input_dir: Path, output_dir: Path, config: PipelineConfig) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    csv_paths = sorted(input_dir.rglob("*_ch02_data.csv"))
    for csv_path in csv_paths:
        stem = image_key(csv_path)
        mask_path = csv_path.with_name(f"{stem}_ch00_mask.png")
        protein_path = csv_path.with_name(f"{stem}_ch02_border.png")
        ext_mean, ext_nuclei = breno_measurement(csv_path)
        row = {
            "dataset": str(csv_path.parent.relative_to(input_dir)),
            "nome_da_imagem": stem,
            "arquivo_csv_breno": str(csv_path.relative_to(input_dir)),
            "media_proteina_breno": ext_mean,
            "nucleos_breno": ext_nuclei,
            "media_proteina_meu_algoritmo": math.nan,
            "nucleos_meu_algoritmo": 0,
            "diferenca_meu_menos_breno": math.nan,
            "diferenca_percentual": math.nan,
            "status": "ok",
        }
        if not mask_path.exists() or not protein_path.exists():
            row["status"] = "imagem_derivada_ausente"
        else:
            try:
                my_mean, my_nuclei = measure_with_pipeline(
                    mask_path, protein_path, config
                )
                delta, relative = difference(my_mean, ext_mean)
                row.update(
                    {
                        "media_proteina_meu_algoritmo": my_mean,
                        "nucleos_meu_algoritmo": my_nuclei,
                        "diferenca_meu_menos_breno": delta,
                        "diferenca_percentual": relative,
                    }
                )
            except (OSError, ValueError, ZeroDivisionError) as error:
                row["status"] = f"erro: {error}"
        rows.append(row)

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_output = output_dir / "comparacao_results13062022.csv"
    fields = list(rows[0]) if rows else []
    with csv_output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    common = [
        row
        for row in rows
        if row["status"] == "ok"
        and np.isfinite(row["media_proteina_breno"])
        and np.isfinite(row["media_proteina_meu_algoritmo"])
    ]
    breno = np.asarray([row["media_proteina_breno"] for row in common])
    mine = np.asarray([row["media_proteina_meu_algoritmo"] for row in common])
    delta = mine - breno
    summary = {
        "input_dir": str(input_dir),
        "pipeline_input_note": "PNG derivados: ch00_mask e ch02_border; não são TIFFs brutos.",
        "configuration": config.__dict__,
        "csv_files_found": len(rows),
        "images_compared": len(common),
        "images_with_error_or_missing_input": len(rows) - len(common),
        "mean_breno": finite_mean(list(breno)),
        "mean_meu_algoritmo": finite_mean(list(mine)),
        "mean_absolute_error": finite_mean(list(np.abs(delta))),
        "mean_absolute_relative_error_percent": finite_mean(
            list(np.abs(delta / breno) * 100)
        )
        if np.all(breno != 0)
        else None,
        "mean_delta_meu_menos_breno": finite_mean(list(delta)),
        "images_within_10_percent": int(
            np.count_nonzero(np.abs(delta / breno) <= 0.10)
        )
        if np.all(breno != 0)
        else None,
        "pearson_correlation": float(np.corrcoef(breno, mine)[0, 1])
        if len(common) > 1
        else None,
    }
    (output_dir / "comparacao_results13062022_resumo.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    markdown = [
        "# Comparação results13062022",
        "",
        "A média do Breno é a média da coluna `intensidade` de cada CSV. A média do meu algoritmo foi calculada usando a segmentação de `pipeline_melhorado.py` sobre `ch00_mask.png` e a média do canal vermelho de `ch02_border.png`, ignorando os pixels brancos do contorno desenhado.",
        "",
        "> Limitação: `results13062022` não contém os TIFFs brutos. Esta é uma comparação de compatibilidade com os PNGs derivados disponíveis, não uma execução nos arquivos originais.",
        "",
        "## Resumo",
        "",
        f"- Arquivos CSV encontrados: **{summary['csv_files_found']}**.",
        f"- Imagens comparadas: **{summary['images_compared']}**.",
        f"- Erro absoluto médio: **{summary['mean_absolute_error']:.3f}**.",
        f"- Erro relativo absoluto médio: **{summary['mean_absolute_relative_error_percent']:.3f}%**.",
        f"- Imagens dentro de ±10%: **{summary['images_within_10_percent']} de {summary['images_compared']}**.",
        "",
        "## Tabela completa",
        "",
        "| Dataset | Nome da imagem | Média Breno | Média meu algoritmo | Diferença | Diferença % | N Breno | N meu algoritmo | Status |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        def fmt(value: object, digits: int = 3) -> str:
            try:
                number = float(value)
            except (TypeError, ValueError):
                return str(value)
            return "—" if not np.isfinite(number) else f"{number:.{digits}f}"

        markdown.append(
            "| {dataset} | {name} | {breno} | {mine} | {delta} | {relative} | {nb} | {nm} | {status} |".format(
                dataset=row["dataset"],
                name=row["nome_da_imagem"],
                breno=fmt(row["media_proteina_breno"]),
                mine=fmt(row["media_proteina_meu_algoritmo"]),
                delta=fmt(row["diferenca_meu_menos_breno"]),
                relative=fmt(row["diferenca_percentual"]),
                nb=fmt(row["nucleos_breno"], 0),
                nm=fmt(row["nucleos_meu_algoritmo"], 0),
                status=row["status"],
            )
        )
    (output_dir / "comparacao_results13062022.md").write_text(
        "\n".join(markdown) + "\n", encoding="utf-8"
    )
    return rows, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("resultados_tcc"))
    parser.add_argument("--min-nucleus-area", type=int, default=100)
    args = parser.parse_args()
    config = PipelineConfig(min_nucleus_area=args.min_nucleus_area)
    _, summary = run(args.input_dir, args.output_dir, config)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
