"""Testes de regressão para as invariantes do pipeline revisado."""

from pathlib import Path
import unittest

import numpy as np

from pipeline_melhorado import build_manifest, pairing_key, read_channel


NUCLEI_DIR = Path("imagens_nucleos")
PROTEIN_DIR = Path("imagens_proteinas")


class PipelineRegressionTests(unittest.TestCase):
    def test_pairing_key_accepts_both_suffix_formats(self) -> None:
        self.assertEqual(
            pairing_key(Path("amostra_Series001_z0_ch00.tif")),
            pairing_key(Path("amostra_Series001_z0_ch02.tif")),
        )
        self.assertEqual(
            pairing_key(Path("amostra_Image007_ch00.tif")),
            pairing_key(Path("amostra_Image007_ch02.tif")),
        )

    def test_dataset_has_43_complete_pairs(self) -> None:
        pairs = build_manifest(NUCLEI_DIR, PROTEIN_DIR)
        self.assertEqual(len(pairs), 43)
        self.assertTrue(all(pair.nucleus_path and pair.protein_path for pair in pairs))

    def test_dataset_channels_are_not_swapped(self) -> None:
        pair = build_manifest(NUCLEI_DIR, PROTEIN_DIR)[0]
        nucleus = read_channel(pair.nucleus_path, 0)
        protein = read_channel(pair.protein_path, 2)
        self.assertGreater(float(np.count_nonzero(nucleus)), 0)
        self.assertGreater(float(np.count_nonzero(protein)), 0)


if __name__ == "__main__":
    unittest.main()
