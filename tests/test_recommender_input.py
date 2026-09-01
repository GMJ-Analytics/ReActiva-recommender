import unittest
from unittest.mock import patch

import pandas as pd

from reactiva.recommender.recommender import (
    recommend_user_based_inactive_customers,
)


class TestRecommenderInput(unittest.TestCase):

    @patch(
        "reactiva.recommender.recommender.cargar_datos"
    )
    @patch(
        "reactiva.recommender.recommender.clean_and_save_dataset",
        side_effect=lambda df: df.copy(),
    )
    def test_supplied_dataframe_is_used_without_reloading_dataset(
        self,
        clean_mock,
        load_mock,
    ):
        supplied_df = pd.DataFrame(
            {
                "Customer ID": [
                    "CUST-001",
                ],
                "Purchase Date": [
                    "2026-08-31",
                ],
            }
        )

        result = (
            recommend_user_based_inactive_customers(
                df=supplied_df,
                persist_predictions=False,
                reference_date="2026-09-01",
            )
        )

        load_mock.assert_not_called()

        clean_mock.assert_called_once()

        pd.testing.assert_frame_equal(
            clean_mock.call_args.args[0],
            supplied_df,
        )

        self.assertTrue(
            result.empty
        )

    @patch(
        "reactiva.recommender.recommender.cargar_datos"
    )
    @patch(
        "reactiva.recommender.recommender.clean_and_save_dataset",
        side_effect=lambda df: df.copy(),
    )
    def test_dataset_path_is_loaded_when_dataframe_is_not_supplied(
        self,
        clean_mock,
        load_mock,
    ):
        loaded_df = pd.DataFrame(
            {
                "Customer ID": [
                    "CUST-001",
                ],
                "Purchase Date": [
                    "2026-08-31",
                ],
            }
        )

        load_mock.return_value = (
            loaded_df.copy()
        )

        result = (
            recommend_user_based_inactive_customers(
                df="fake-dataset.csv",
                persist_predictions=False,
                reference_date="2026-09-01",
            )
        )

        load_mock.assert_called_once_with(
            "fake-dataset.csv"
        )

        clean_mock.assert_called_once()

        pd.testing.assert_frame_equal(
            clean_mock.call_args.args[0],
            loaded_df,
        )

        self.assertTrue(
            result.empty
        )


if __name__ == "__main__":
    unittest.main()