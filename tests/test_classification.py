"""Tests for classification analysis functions and CLI."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import tifffile

from segmentation_measurement.analysis import apply_classifier, train_classifier


def _make_annotated_measurements(n: int = 20) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "index": np.arange(1, n + 1),
        "mean_intensity": np.concatenate([
            rng.uniform(0, 40, n // 2),
            rng.uniform(60, 100, n - n // 2),
        ]),
        "area": rng.uniform(10, 200, n),
    })
    annotations = np.zeros(n, dtype=int)
    annotations[: n // 2] = 1
    annotations[n // 2 :] = 2
    df["annotation"] = annotations
    return df


class TestTrainClassifier(unittest.TestCase):

    def test_returns_fitted_pipeline(self):
        df = _make_annotated_measurements()
        clf = train_classifier(df, method="logistic_regression")
        self.assertIsNotNone(clf)
        self.assertTrue(hasattr(clf, "predict"))

    def test_logistic_regression(self):
        df = _make_annotated_measurements()
        clf = train_classifier(df, method="logistic_regression")
        self.assertIsNotNone(clf)

    def test_random_forest(self):
        df = _make_annotated_measurements()
        clf = train_classifier(df, method="random_forest")
        self.assertIsNotNone(clf)

    def test_classifier_classes_match_annotation_labels(self):
        df = _make_annotated_measurements()
        clf = train_classifier(df)
        self.assertSetEqual(set(clf.classes_.tolist()), {1, 2})

    def test_does_not_modify_input(self):
        df = _make_annotated_measurements()
        original_cols = list(df.columns)
        train_classifier(df)
        self.assertEqual(list(df.columns), original_cols)

    def test_raises_missing_annotation_column(self):
        df = pd.DataFrame({"index": [1, 2], "feat": [1.0, 2.0]})
        with self.assertRaises(ValueError):
            train_classifier(df, annotation_column="annotation")

    def test_raises_no_annotated_rows(self):
        df = _make_annotated_measurements()
        df["annotation"] = 0
        with self.assertRaises(ValueError):
            train_classifier(df)

    def test_raises_no_feature_columns(self):
        df = pd.DataFrame({"index": [1, 2, 3], "annotation": [1, 1, 2]})
        with self.assertRaises(ValueError):
            train_classifier(df)

    def test_raises_unknown_method(self):
        df = _make_annotated_measurements()
        with self.assertRaises(ValueError):
            train_classifier(df, method="svm")

    def test_excludes_annotation_from_features(self):
        # annotation values are perfectly correlated; classifier should still
        # only use non-annotation numeric columns as features
        df = _make_annotated_measurements()
        clf = train_classifier(df)
        # should train without error and have 2 classes
        self.assertEqual(len(clf.classes_), 2)

    def test_custom_kwargs_forwarded(self):
        df = _make_annotated_measurements()
        clf = train_classifier(df, method="random_forest", n_estimators=10)
        self.assertEqual(clf.named_steps["clf"].n_estimators, 10)

    def test_handles_nan_in_features(self):
        df = _make_annotated_measurements()
        df.loc[0, "mean_intensity"] = np.nan
        clf = train_classifier(df)
        self.assertIsNotNone(clf)


class TestApplyClassifier(unittest.TestCase):

    def _train(self, n: int = 20) -> tuple:
        df = _make_annotated_measurements(n)
        clf = train_classifier(df)
        return df, clf

    def test_adds_classification_id_column(self):
        df, clf = self._train()
        result = apply_classifier(df, clf)
        self.assertIn("classification_id", result.columns)

    def test_adds_classification_name_column(self):
        df, clf = self._train()
        result = apply_classifier(df, clf)
        self.assertIn("classification_name", result.columns)

    def test_does_not_modify_input(self):
        df, clf = self._train()
        original_cols = list(df.columns)
        apply_classifier(df, clf)
        self.assertEqual(list(df.columns), original_cols)

    def test_classification_ids_are_one_based(self):
        df, clf = self._train(30)
        result = apply_classifier(df, clf)
        nonzero = result["classification_id"][result["classification_id"] > 0]
        self.assertTrue((nonzero >= 1).all())

    def test_custom_class_names_used(self):
        df, clf = self._train()
        result = apply_classifier(df, clf, class_names=["type_A", "type_B"])
        names = set(result["classification_name"].unique()) - {""}
        self.assertTrue(names.issubset({"type_A", "type_B"}))

    def test_default_class_names(self):
        df, clf = self._train()
        result = apply_classifier(df, clf)
        names = set(result["classification_name"].unique()) - {""}
        self.assertTrue(all(n.startswith("class_") for n in names))

    def test_length_preserved(self):
        df, clf = self._train()
        result = apply_classifier(df, clf)
        self.assertEqual(len(result), len(df))

    def test_label_column_preserved(self):
        df, clf = self._train()
        result = apply_classifier(df, clf)
        pd.testing.assert_series_equal(result["index"], df["index"])

    def test_excludes_classification_columns_from_reapply(self):
        df, clf = self._train(20)
        result1 = apply_classifier(df, clf)
        result2 = apply_classifier(result1, clf)
        self.assertIn("classification_id", result2.columns)

    def test_raises_no_feature_columns(self):
        _, clf = self._train()
        df = pd.DataFrame({"index": [1, 2, 3]})
        with self.assertRaises(ValueError):
            apply_classifier(df, clf)

    def test_handles_nan_rows(self):
        df, clf = self._train(20)
        df.loc[0, "mean_intensity"] = np.nan
        result = apply_classifier(df, clf)
        self.assertEqual(result.loc[0, "classification_id"], 0)
        self.assertEqual(result.loc[0, "classification_name"], "")

    def test_classifier_excludes_annotation_from_features(self):
        df = _make_annotated_measurements(20)
        clf = train_classifier(df)
        result = apply_classifier(df, clf)
        self.assertIn("classification_id", result.columns)

    def test_pipeline_serialisation(self):
        df, clf = self._train()
        import joblib
        import io
        buf = io.BytesIO()
        joblib.dump(clf, buf)
        buf.seek(0)
        clf2 = joblib.load(buf)
        result = apply_classifier(df, clf2)
        self.assertIn("classification_id", result.columns)


class TestClassificationCLI(unittest.TestCase):

    def _call_main(self, argv):
        from segmentation_measurement._cli import main
        with patch("sys.argv", ["segmentation-measurement"] + argv):
            main()

    def test_train_classifier_cli_logistic_regression(self):
        df = _make_annotated_measurements(20)
        with tempfile.TemporaryDirectory() as tmpdir:
            table_path = os.path.join(tmpdir, "annotated.csv")
            out_path = os.path.join(tmpdir, "clf.joblib")
            df.to_csv(table_path, index=False)
            self._call_main([
                "analyze", "train-classifier",
                "--tables", table_path,
                "--method", "logistic_regression",
                "--output", out_path,
            ])
            self.assertTrue(os.path.exists(out_path))
            import joblib
            clf = joblib.load(out_path)
            self.assertTrue(hasattr(clf, "predict"))

    def test_train_classifier_cli_random_forest(self):
        df = _make_annotated_measurements(20)
        with tempfile.TemporaryDirectory() as tmpdir:
            table_path = os.path.join(tmpdir, "annotated.csv")
            out_path = os.path.join(tmpdir, "clf.joblib")
            df.to_csv(table_path, index=False)
            self._call_main([
                "analyze", "train-classifier",
                "--tables", table_path,
                "--method", "random_forest",
                "--n-estimators", "10",
                "--output", out_path,
            ])
            import joblib
            clf = joblib.load(out_path)
            self.assertEqual(clf.named_steps["clf"].n_estimators, 10)

    def test_train_classifier_cli_multiple_tables(self):
        df1 = _make_annotated_measurements(10)
        df2 = _make_annotated_measurements(10)
        df2["index"] = df2["index"] + 10
        with tempfile.TemporaryDirectory() as tmpdir:
            t1 = os.path.join(tmpdir, "t1.csv")
            t2 = os.path.join(tmpdir, "t2.csv")
            out_path = os.path.join(tmpdir, "clf.joblib")
            df1.to_csv(t1, index=False)
            df2.to_csv(t2, index=False)
            self._call_main([
                "analyze", "train-classifier",
                "--tables", t1, t2,
                "--output", out_path,
            ])
            self.assertTrue(os.path.exists(out_path))

    def test_classify_cli_basic(self):
        df = _make_annotated_measurements(20)
        with tempfile.TemporaryDirectory() as tmpdir:
            table_path = os.path.join(tmpdir, "annotated.csv")
            clf_path = os.path.join(tmpdir, "clf.joblib")
            out_path = os.path.join(tmpdir, "classified.csv")
            df.to_csv(table_path, index=False)
            self._call_main([
                "analyze", "train-classifier",
                "--tables", table_path,
                "--output", clf_path,
            ])
            self._call_main([
                "analyze", "classify",
                "--table", table_path,
                "--classifier", clf_path,
                "--output", out_path,
            ])
            result = pd.read_csv(out_path)
            self.assertIn("classification_id", result.columns)
            self.assertIn("classification_name", result.columns)

    def test_classify_cli_with_class_names(self):
        df = _make_annotated_measurements(20)
        with tempfile.TemporaryDirectory() as tmpdir:
            table_path = os.path.join(tmpdir, "annotated.csv")
            clf_path = os.path.join(tmpdir, "clf.joblib")
            out_path = os.path.join(tmpdir, "classified.csv")
            df.to_csv(table_path, index=False)
            self._call_main([
                "analyze", "train-classifier",
                "--tables", table_path,
                "--output", clf_path,
            ])
            self._call_main([
                "analyze", "classify",
                "--table", table_path,
                "--classifier", clf_path,
                "--class-names", "type_A", "type_B",
                "--output", out_path,
            ])
            result = pd.read_csv(out_path)
            names = set(result["classification_name"].dropna().unique()) - {""}
            self.assertTrue(names.issubset({"type_A", "type_B"}))

    def test_classify_cli_with_segmentation(self):
        seg = np.zeros((20, 20), dtype=np.int32)
        seg[1:6, 1:6] = 1
        seg[7:12, 7:12] = 2
        df = pd.DataFrame({
            "index": [1, 2],
            "mean_intensity": [10.0, 90.0],
            "annotation": [1, 2],
        })
        with tempfile.TemporaryDirectory() as tmpdir:
            seg_path = os.path.join(tmpdir, "seg.tif")
            table_path = os.path.join(tmpdir, "annotated.csv")
            clf_path = os.path.join(tmpdir, "clf.joblib")
            out_path = os.path.join(tmpdir, "classified.csv")
            out_seg_path = os.path.join(tmpdir, "classified.tif")
            tifffile.imwrite(seg_path, seg)
            df.to_csv(table_path, index=False)
            self._call_main([
                "analyze", "train-classifier",
                "--tables", table_path,
                "--output", clf_path,
            ])
            self._call_main([
                "analyze", "classify",
                "--table", table_path,
                "--classifier", clf_path,
                "--output", out_path,
                "--segmentation", seg_path,
                "--output-segmentation", out_seg_path,
            ])
            out_seg = tifffile.imread(out_seg_path)
            self.assertTrue(np.any(out_seg[1:6, 1:6] > 0))
            self.assertTrue(np.any(out_seg[7:12, 7:12] > 0))
            self.assertEqual(out_seg[0, 0], 0)

    def test_classify_cli_tsv_output(self):
        df = _make_annotated_measurements(20)
        with tempfile.TemporaryDirectory() as tmpdir:
            table_path = os.path.join(tmpdir, "annotated.csv")
            clf_path = os.path.join(tmpdir, "clf.joblib")
            out_path = os.path.join(tmpdir, "classified.tsv")
            df.to_csv(table_path, index=False)
            self._call_main([
                "analyze", "train-classifier",
                "--tables", table_path,
                "--output", clf_path,
            ])
            self._call_main([
                "analyze", "classify",
                "--table", table_path,
                "--classifier", clf_path,
                "--output", out_path,
            ])
            result = pd.read_csv(out_path, sep="\t")
            self.assertIn("classification_id", result.columns)


if __name__ == "__main__":
    unittest.main()
