import pandas as pd
import pytest

from healthai.data import validate_columns


def test_validate_columns_accepts_complete_dataframe() -> None:
    dataframe = pd.DataFrame({"Glucose": [100], "Outcome": [0]})

    validate_columns(dataframe, ["Glucose", "Outcome"])


def test_validate_columns_reports_missing_columns() -> None:
    dataframe = pd.DataFrame({"Glucose": [100]})

    with pytest.raises(ValueError, match="Outcome"):
        validate_columns(dataframe, ["Glucose", "Outcome"])

