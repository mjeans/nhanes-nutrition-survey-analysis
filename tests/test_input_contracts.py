import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_analysis as analysis


class InputContractTests(unittest.TestCase):
    def test_duplicate_person_keys_fail_before_analysis(self):
        def source(name, columns):
            return pd.DataFrame({c: [1., 1.] for c in columns})
        with patch.object(analysis, "read_source", side_effect=source):
            with self.assertRaises(pd.errors.MergeError):
                analysis.build_analysis_frame()

    def test_missing_person_keys_fail_before_analysis(self):
        def source(name, columns):
            result = pd.DataFrame({c: [1., 2.] for c in columns})
            result.loc[0, "SEQN"] = float("nan")
            return result
        with patch.object(analysis, "read_source", side_effect=source):
            with self.assertRaisesRegex(ValueError, "identifiers"):
                analysis.build_analysis_frame()

    def test_bad_cached_download_is_rejected_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "DEMO_J.XPT").write_bytes(b"not the verified CDC payload")
            with patch.object(analysis, "DATA_DIR", path), patch("urllib.request.urlopen") as network:
                with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
                    analysis.download_file("DEMO_J.XPT", analysis.SOURCES["DEMO_J.XPT"])
                network.assert_not_called()
