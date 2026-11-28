import datetime
import unittest
from unittest.mock import patch

import pandas as pd
from pandas.testing import assert_frame_equal

from data_processor import (
    add_or_update_rainfall_record,
    parse_rainfall_csv,
    save_bulk_monthly_records,
)


def fixture():
    return parse_rainfall_csv(
        "Tahun,2026,No. Stasiun :,Uji A\nTgl,Jan\n"
        "1,0\n2,\n3,RUSAK\n4,6\n"
        "Tahun,2026,No. Stasiun :,Uji B\nTgl,Jan\n1,2\n"
    )


class MonthlyEntryTest(unittest.TestCase):
    def setUp(self):
        self.original = fixture()
        self.log = self.enterContext(patch("data_processor.log_manual_entry"))

    def save(self, items):
        return save_bulk_monthly_records(self.original, "uji a", 2026, 1, items)

    def test_no_change_no_write_or_log(self):
        saved = self.save([
            {"Hari": 1, "Curah_Hujan": 0.0, "Status": "Normal"},
            {"Hari": 2, "Curah_Hujan": float("nan"), "Status": "Normal"},
            {"Hari": 3, "Curah_Hujan": None, "Status": "RUSAK"},
            {"Hari": 4, "Curah_Hujan": 6, "Status": "Normal"},
            {"Hari": 5, "Curah_Hujan": None, "Status": "Belum Ada Data"},
        ])
        self.assertIs(saved, self.original)
        self.log.assert_not_called()

    def test_partial_save_preserves_other_days_and_stations(self):
        saved = self.save([{"Hari": 2, "Curah_Hujan": 12.5}])
        keep = lambda frame: frame.loc[~(
            (frame["Stasiun"] == "Uji A") & (frame["Bulan"] == 1) & (frame["Hari"] == 2)
        )].reset_index(drop=True)
        assert_frame_equal(keep(saved), keep(self.original))
        self.assertEqual(saved.loc[(saved["Stasiun"] == "Uji A") & (saved["Bulan"] == 1) & (saved["Hari"] == 2), "Curah_Hujan"].item(), 12.5)
        self.log.assert_called_once_with("Uji A", "2026-01", "1 hari", "BULK", "-", "BULK_UPDATE")

    def test_clearing_reading_is_missing_not_zero(self):
        saved = self.save([{"Hari": 4, "Curah_Hujan": None, "Status": "Normal"}])
        row = saved.loc[(saved["Stasiun"] == "Uji A") & (saved["Bulan"] == 1) & (saved["Hari"] == 4)].iloc[0]
        self.assertTrue(pd.isna(row["Curah_Hujan"]))
        self.assertEqual(row["Status"], "Belum Ada Data")

    def test_single_entry_requires_measurement_or_broken_sensor(self):
        date = datetime.date(2026, 1, 2)
        with self.assertRaises(ValueError):
            add_or_update_rainfall_record(self.original, "Uji A", date)
        self.log.assert_not_called()
        for value, status in [(0.0, "Normal"), (None, "RUSAK")]:
            saved = add_or_update_rainfall_record(self.original, "Uji A", date, value, status)
            row = saved.loc[(saved["Stasiun"] == "Uji A") & (saved["Bulan"] == 1) & (saved["Hari"] == 2)].iloc[0]
            self.assertEqual(row["Status"], status)
            self.assertTrue(pd.isna(row["Curah_Hujan"]) if value is None else row["Curah_Hujan"] == value)


if __name__ == "__main__":
    unittest.main()
