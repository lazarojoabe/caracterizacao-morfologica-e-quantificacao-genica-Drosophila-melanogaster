"""Pipeline reproduzível para segmentação nuclear e quantificação de proteína.

Esta implementação é mantida separada dos scripts originais para permitir uma
comparação auditável entre o método da iniciação científica e o método revisado.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


LOGGER = logging.getLogger("pipeline_melhorado")
CHANNEL_SUFFIX = re.compile(r"(?:_z0)?_ch(?P<channel>00|02)\.tif$", re.IGNORECASE)


@dataclass(frozen=True)
class SamplePair:
    key: str
    nucleus_path: Path | None
    protein_path: Path | None


@dataclass(frozen=True)
class PipelineConfig:
    nucleus_channel: int = 0
    protein_channel: int = 2
    gaussian_kernel: int = 5
    gaussian_sigma: float = 1.0
    opening_kernel: int = 3
    closing_kernel: int = 5
    min_nucleus_area: int = 100


def pairing_key(path: Path) -> str:
    """Remove apenas o sufixo de canal, aceitando os dois padrões do dataset."""

    match = CHANNEL_SUFFIX.search(path.name)
    if not match:
        raise ValueError(f"Nome sem sufixo de canal reconhecível: {path.name}")
    return path.name[: match.start()]


def _index_channel(directory: Path, expected_channel: str) -> dict[str, Path]:
    indexed: dict[str, Path] = {}
    for path in sorted(directory.glob("*.tif")):
        match = CHANNEL_SUFFIX.search(path.name)
        if not match or match.group("channel") != expected_channel:
            continue
        key = pairing_key(path)
        if key in indexed:
            raise ValueError(f"Arquivo duplicado para a chave {key!r}: {path.name}")
        indexed[key] = path
    return indexed


def build_manifest(nucleus_dir: Path, protein_dir: Path) -> list[SamplePair]:
    """Cria pares por chave normalizada e preserva amostras incompletas."""

    nuclei = _index_channel(nucleus_dir, "00")
    proteins = _index_channel(protein_dir, "02")
    pairs = []
    for key in sorted(set(nuclei) | set(proteins)):
        pairs.append(SamplePair(key, nuclei.get(key), proteins.get(key)))
    return pairs


def read_channel(path: Path, channel: int) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise IOError(f"Não foi possível ler a imagem: {path}")
    if image.ndim == 2:
        if channel != 0:
            raise ValueError(f"Imagem monocanal não possui o canal {channel}: {path}")
        return image.astype(np.float32)
    if image.ndim != 3 or image.shape[2] <= channel:
        raise ValueError(f"Formato/canal incompatível em {path}: {image.shape}")
    return image[:, :, channel].astype(np.float32)


def _odd(value: int) -> int:
    if value < 1 or value % 2 == 0:
        raise ValueError(f"O tamanho do kernel deve ser ímpar e positivo: {value}")
    return value


def segment_nuclei(signal: np.ndarray, config: PipelineConfig) -> tuple[np.ndarray, np.ndarray, float]:
    """Segmenta núcleos e retorna (labels, máscara, threshold de Otsu).

    A máscara permanece monocanal. Sobreposições coloridas são geradas apenas
    para controle visual, nunca usadas para medir intensidade.
    """

    image = np.clip(signal, 0, 255).astype(np.uint8)
    blurred = cv2.GaussianBlur(
        image,
        (_odd(config.gaussian_kernel), _odd(config.gaussian_kernel)),
        config.gaussian_sigma,
    )
    threshold, binary = cv2.threshold(
        blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    open_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (_odd(config.opening_kernel), _odd(config.opening_kernel))
    )
    close_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (_odd(config.closing_kernel), _odd(config.closing_kernel))
    )
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, open_kernel)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, close_kernel)

    count, component_labels, stats, _ = cv2.connectedComponentsWithStats(
        cleaned, connectivity=8
    )
    keep = stats[:, cv2.CC_STAT_AREA] >= config.min_nucleus_area
    keep[0] = False
    remapped_ids = np.zeros(count, dtype=np.int32)
    remapped_ids[keep] = np.arange(1, int(np.count_nonzero(keep)) + 1)
    labels = remapped_ids[component_labels]
    mask = np.where(labels > 0, 255, 0).astype(np.uint8)
    return labels, mask, float(threshold)


def measure_sample(
    pair: SamplePair,
    config: PipelineConfig,
    output_dir: Path,
) -> tuple[list[dict], dict]:
    if pair.nucleus_path is None or pair.protein_path is None:
        return [], {
            "sample_key": pair.key,
            "status": "incomplete_pair",
            "nucleus_count": 0,
        }

    nucleus_signal = read_channel(pair.nucleus_path, config.nucleus_channel)
    protein_signal = read_channel(pair.protein_path, config.protein_channel)
    if nucleus_signal.shape != protein_signal.shape:
        raise ValueError(
            f"Dimensões incompatíveis para {pair.key}: "
            f"{nucleus_signal.shape} vs {protein_signal.shape}"
        )

    labels, mask, threshold = segment_nuclei(nucleus_signal, config)
    rows: list[dict] = []
    for nucleus_id in range(1, int(labels.max()) + 1):
        nucleus_mask = labels == nucleus_id
        values = protein_signal[nucleus_mask]
        if values.size == 0:
            continue
        signal_mean = float(values.mean())
        signal_median = float(np.median(values))
        rows.append(
            {
                "sample_key": pair.key,
                "nucleus_id": nucleus_id,
                "area_px": int(values.size),
                "signal_mean_raw": signal_mean,
                "signal_median_raw": signal_median,
                "signal_std_raw": float(values.std()),
                "integrated_intensity_raw": float(values.sum()),
            }
        )

    if rows:
        summary = {
            "sample_key": pair.key,
            "status": "ok",
            "nucleus_count": len(rows),
            "otsu_threshold": threshold,
            "area_total_px": int(sum(row["area_px"] for row in rows)),
            "mean_raw_red_per_nucleus": float(
                np.mean([row["signal_mean_raw"] for row in rows])
            ),
        }
    else:
        summary = {
            "sample_key": pair.key,
            "status": "no_nuclei_detected",
            "nucleus_count": 0,
            "otsu_threshold": threshold,
        }

    mask_dir = output_dir / "mascaras_melhoradas"
    overlay_dir = output_dir / "overlays_melhorados"
    mask_dir.mkdir(parents=True, exist_ok=True)
    overlay_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_.+-]", "_", pair.key)
    if not cv2.imwrite(str(mask_dir / f"{safe_name}.png"), mask):
        raise IOError(f"Falha ao gravar máscara de {pair.key}")
    normalized = cv2.normalize(np.clip(protein_signal, 0, 255).astype(np.uint8), None, 0, 255, cv2.NORM_MINMAX)
    overlay = cv2.cvtColor(normalized, cv2.COLOR_GRAY2BGR)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(overlay, contours, -1, (0, 255, 0), 1)
    if not cv2.imwrite(str(overlay_dir / f"{safe_name}.png"), overlay):
        raise IOError(f"Falha ao gravar overlay de {pair.key}")
    return rows, summary


def write_csv(path: Path, rows: Iterable[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_pipeline(
    nucleus_dir: Path,
    protein_dir: Path,
    output_dir: Path,
    config: PipelineConfig,
) -> tuple[list[dict], list[dict]]:
    pairs = build_manifest(nucleus_dir, protein_dir)
    manifest_rows = [
        {
            "sample_key": pair.key,
            "nucleus_file": pair.nucleus_path.name if pair.nucleus_path else "",
            "protein_file": pair.protein_path.name if pair.protein_path else "",
            "status": "paired" if pair.nucleus_path and pair.protein_path else "incomplete_pair",
        }
        for pair in pairs
    ]
    write_csv(
        output_dir / "manifesto_amostras.csv",
        manifest_rows,
        ["sample_key", "nucleus_file", "protein_file", "status"],
    )

    all_rows: list[dict] = []
    summaries: list[dict] = []
    for index, pair in enumerate(pairs, start=1):
        LOGGER.info("Processando %d/%d: %s", index, len(pairs), pair.key)
        rows, summary = measure_sample(pair, config, output_dir)
        all_rows.extend(rows)
        summaries.append(summary)

    if all_rows:
        write_csv(
            output_dir / "resultados_por_nucleo.csv",
            all_rows,
            list(all_rows[0].keys()),
        )
    else:
        write_csv(
            output_dir / "resultados_por_nucleo.csv",
            [],
            [
                "sample_key",
                "nucleus_id",
                "area_px",
                "signal_mean_raw",
                "signal_median_raw",
                "signal_std_raw",
                "integrated_intensity_raw",
            ],
        )
    write_csv(
        output_dir / "resumo_por_amostra.csv",
        summaries,
        sorted({key for summary in summaries for key in summary}),
    )
    (output_dir / "configuracao.json").write_text(
        json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return all_rows, summaries


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nuclei-dir", type=Path, default=Path("imagens_nucleos"))
    parser.add_argument("--protein-dir", type=Path, default=Path("imagens_proteinas"))
    parser.add_argument("--output-dir", type=Path, default=Path("resultados_tcc"))
    parser.add_argument("--min-nucleus-area", type=int, default=100)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s: %(message)s")
    config = PipelineConfig(
        min_nucleus_area=args.min_nucleus_area,
    )
    run_pipeline(args.nuclei_dir, args.protein_dir, args.output_dir, config)
    LOGGER.warning("Resultados gravados em %s", args.output_dir)


if __name__ == "__main__":
    main()
