"""Behavior checks for the integration's main integrity risks."""
import importlib.util
import unittest
from pathlib import Path

import pandas as pd
import pyarrow as pa

spec = importlib.util.spec_from_file_location(
    "final_jury_preparation", Path(__file__).resolve().parents[1] / "tools" / "prepare_data.py")
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)


class PreparationIntegrityTests(unittest.TestCase):
    def test_age_bands_never_invent_exact_ages(self):
        values = pd.Series(["[10-20)", "18 to 29", "[40-50)", "70 or Older", "unknown"], dtype="string")
        result = prep.age_common(values)
        self.assertEqual(result.iloc[:4].tolist(), ["0-29", "0-29", "30-49", "70+"])
        self.assertTrue(pd.isna(result.iloc[4]))

    def test_2024_hyphenated_age_bands_match_2023_band_definitions(self):
        values = pd.Series(["0-17", "18-29", "30-49", "50-69", "70 or Older"], dtype="string")
        self.assertEqual(prep.age_common(values).tolist(), ["0-29", "0-29", "30-49", "50-69", "70+"])

    def test_top_coded_stay_is_flagged_and_invalid_durations_remain_missing(self):
        lower, top = prep.parse_los(pd.Series(["120+", "3", "0", "-1", "1.5", "redacted"], dtype="string"))
        self.assertEqual(lower.iloc[:3].tolist(), [120, 3, 0])
        self.assertEqual(top.tolist(), [True, False, False, False, False, False])
        self.assertTrue(lower.iloc[3:].isna().all())

    def test_publisher_spaced_top_code_keeps_its_lower_bound(self):
        lower, top = prep.parse_los(pd.Series(["120 +", " 120 + ", "120+"], dtype="string"))
        self.assertEqual(lower.tolist(), [120, 120, 120])
        self.assertTrue(top.all())

    def test_money_handles_separators_without_turning_missing_into_zero(self):
        values = prep.parse_money(pd.Series(["$1,234.56", "0", "-3.20", "", "inf"], dtype="string"))
        self.assertAlmostEqual(values.iloc[0], 1234.56)
        self.assertEqual(values.iloc[1], 0)
        self.assertEqual(values.iloc[2], -3.2)
        self.assertTrue(values.iloc[3:].isna().all())

    def test_external_rows_cannot_inherit_or_invent_readmission_outcomes(self):
        raw = pd.DataFrame({"source_row_id": ["row-same"], "gender": ["F"],
                            "age_group": ["18 to 29"], "length_of_stay": ["120+"],
                            "readmitted": ["<30"], "patient_nbr": ["123"]}, dtype="string")
        normalized = prep.normalize(raw, "SPARCS_2023", 2023)
        self.assertTrue(normalized["readmission_label"].isna().all())
        self.assertFalse(normalized["readmission_observed"].any())
        self.assertTrue(normalized["patient_key"].isna().all())
        self.assertEqual(normalized["gender"].iloc[0], "Female")

    def test_same_row_identifier_from_different_sources_cannot_collide(self):
        raw = pd.DataFrame({"source_row_id": ["same"]}, dtype="string")
        a = prep.normalize(raw, "SPARCS_2023", 2023)
        b = prep.normalize(raw, "SPARCS_2024", 2024)
        self.assertNotEqual(a["encounter_key"].iloc[0], b["encounter_key"].iloc[0])

    def test_uci_has_no_invented_calendar_year_facility_or_cost(self):
        raw = pd.DataFrame({"encounter_id": ["1"], "patient_nbr": ["2"], "age": ["[70-80)"],
                            "admission_type_id": ["1"], "discharge_disposition_id": ["1"],
                            "readmitted": [">30"], "time_in_hospital": ["4"]}, dtype="string")
        normalized = prep.normalize(raw, "UCI_DIABETES")
        self.assertEqual(normalized["readmission_label"].iloc[0], ">30")
        self.assertTrue(normalized["readmission_observed"].iloc[0])
        for field in ["discharge_year", "facility_key", "total_costs_usd"]:
            self.assertTrue(normalized[field].isna().all())
        self.assertEqual(normalized["admission_type_common"].iloc[0], "Emergency")

    def test_all_null_columns_keep_same_parquet_types_across_sources(self):
        raw = pd.DataFrame({"source_row_id": ["a"]}, dtype="string")
        table = prep.as_table(prep.normalize(raw, "SPARCS_2024", 2024))
        self.assertEqual(table.schema, prep.SCHEMA)
        self.assertEqual(table.schema.field("readmission_label").type, pa.string())
        self.assertEqual(table.schema.field("discharge_year").type, pa.int16())


if __name__ == "__main__":
    unittest.main()
