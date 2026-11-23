from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


SUPPORTED_EXTENSIONS = {".tif", ".tiff", ".png", ".jpg", ".jpeg"}
MAX_UPLOAD_BYTES = 250 * 1024 * 1024
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.()\-+ ]+")
_DERIVED_MARKERS = ("_border", "_mask", "_overlay", "_draw", "binariz", "gaussian", "filled")


@dataclass(frozen=True)
class ImageInfo:
    name: str
    width: int
    height: int
    channels: int
    dtype: str
    derived: bool


def safe_filename(name: str, fallback: str = "image.tif") -> str:
    """Remove caminhos e caracteres perigosos sem confiar no nome do cliente."""

    cleaned = Path(name or fallback).name
    cleaned = _SAFE_NAME.sub("_", cleaned).strip(" .")
    if not cleaned:
        cleaned = fallback
    if Path(cleaned).suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Formato não suportado: {Path(cleaned).suffix or '(sem extensão)'}")
    return cleaned[:180]


def is_derived_name(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in _DERIVED_MARKERS)


def decode_image(data: bytes, name: str) -> tuple[np.ndarray, ImageInfo]:
    if not data:
        raise ValueError(f"Arquivo vazio: {name}")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Arquivo excede o limite de {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    array = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_UNCHANGED)
    if image is None or image.size == 0:
        raise ValueError(f"Arquivo inválido ou corrompido: {name}")
    if image.ndim == 2:
        channels = 1
    elif image.ndim == 3:
        channels = int(image.shape[2])
    else:
        raise ValueError(f"Dimensões não suportadas em {name}: {image.shape}")
    info = ImageInfo(
        name=name,
        width=int(image.shape[1]),
        height=int(image.shape[0]),
        channels=channels,
        dtype=str(image.dtype),
        derived=is_derived_name(name),
    )
    return image, info


def read_channel(image: np.ndarray, channel: int, name: str = "imagem") -> np.ndarray:
    if image.ndim == 2:
        if channel != 0:
            raise ValueError(f"{name} é monocanal; canal {channel} não existe")
        return image.astype(np.float32, copy=False)
    if image.ndim != 3 or channel < 0 or channel >= image.shape[2]:
        raise ValueError(f"{name} não possui o canal {channel}")
    return image[:, :, channel].astype(np.float32, copy=False)


def preview_png(image: np.ndarray, channel: int = 0) -> bytes:
    channel_image = read_channel(image, channel)
    finite = np.nan_to_num(channel_image, nan=0.0)
    if finite.max() > finite.min():
        normalized = cv2.normalize(finite, None, 0, 255, cv2.NORM_MINMAX)
    else:
        normalized = np.zeros_like(finite, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", normalized.astype(np.uint8))
    if not ok:
        raise IOError("Falha ao codificar a prévia da imagem")
    return encoded.tobytes()


def mask_png(labels: np.ndarray) -> bytes:
    mask = np.where(labels > 0, 255, 0).astype(np.uint8)
    ok, encoded = cv2.imencode(".png", mask)
    if not ok:
        raise IOError("Falha ao codificar a máscara")
    return encoded.tobytes()
