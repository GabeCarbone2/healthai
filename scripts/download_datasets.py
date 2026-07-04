"""Baixa e harmoniza os dados públicos Pima e NHANES 2017-2018."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

PIMA_URL = "https://www.openml.org/data/get_csv/37/dataset_37_diabetes.arff"
NHANES_BASE_URL = (
    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles"
)
NHANES_FILES = {
    "demographics": "DEMO_J",
    "body_measures": "BMX_J",
    "blood_pressure": "BPX_J",
    "fasting_glucose": "GLU_J",
    "glycohemoglobin": "GHB_J",
    "total_cholesterol": "TCHOL_J",
    "triglycerides": "TRIGLY_J",
    "insulin": "INS_J",
    "diabetes_questionnaire": "DIQ_J",
}

PIMA_RENAME = {
    "preg": "Pregnancies",
    "plas": "Glucose",
    "pres": "BloodPressure",
    "skin": "SkinThickness",
    "insu": "Insulin",
    "mass": "BMI",
    "pedi": "DiabetesPedigreeFunction",
    "age": "Age",
}

COMBINED_COLUMNS = [
    "source_dataset",
    "participant_id",
    "glucose_mg_dl",
    "glucose_measurement_type",
    "hba1c_percent",
    "bmi_kg_m2",
    "systolic_bp_mmhg",
    "diastolic_bp_mmhg",
    "total_cholesterol_mg_dl",
    "triglycerides_mg_dl",
    "family_history",
    "diabetes_pedigree_function",
    "age_years",
    "sex",
    "race_ethnicity",
    "serum_insulin_muu_ml",
    "insulin_measurement_type",
    "skin_thickness_mm",
    "pregnancies",
    "waist_circumference_cm",
    "diabetes_outcome",
    "diabetes_outcome_definition",
    "fasting_sample_weight",
    "full_sample_mec_weight",
    "survey_psu",
    "survey_stratum",
]


def download(url: str, destination: Path, *, force: bool = False) -> None:
    """Baixa um arquivo, preservando cópias existentes por padrão."""
    if destination.exists() and destination.stat().st_size > 0 and not force:
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "HealthAI-TCC/0.1"})
    with urlopen(request, timeout=120) as response:  # noqa: S310
        with destination.open("wb") as output:
            shutil.copyfileobj(response, output)


def prepare_pima(*, force: bool = False) -> pd.DataFrame:
    """Baixa o Pima, cria o CSV compatível e retorna dados harmonizados."""
    source_path = RAW_DIR / "pima" / "openml_diabetes.csv"
    download(PIMA_URL, source_path, force=force)

    source = pd.read_csv(source_path)
    expected = {*PIMA_RENAME, "class"}
    missing = expected - set(source.columns)
    if missing:
        raise ValueError(f"Colunas inesperadamente ausentes no Pima: {sorted(missing)}")

    compatible = source.rename(columns=PIMA_RENAME)
    compatible["Outcome"] = compatible["class"].map(
        {"tested_negative": 0, "tested_positive": 1}
    )
    compatible = compatible[[*PIMA_RENAME.values(), "Outcome"]]
    compatible.to_csv(RAW_DIR / "diabetes.csv", index=False)

    harmonized = pd.DataFrame(index=compatible.index)
    harmonized["source_dataset"] = "pima_openml_37"
    harmonized["participant_id"] = [
        f"pima_{number:04d}" for number in range(1, len(compatible) + 1)
    ]
    harmonized["glucose_mg_dl"] = compatible["Glucose"].replace(0, np.nan)
    harmonized["glucose_measurement_type"] = "ogtt_2h"
    harmonized["hba1c_percent"] = np.nan
    harmonized["bmi_kg_m2"] = compatible["BMI"].replace(0, np.nan)
    harmonized["systolic_bp_mmhg"] = np.nan
    harmonized["diastolic_bp_mmhg"] = compatible["BloodPressure"].replace(
        0, np.nan
    )
    harmonized["total_cholesterol_mg_dl"] = np.nan
    harmonized["triglycerides_mg_dl"] = np.nan
    harmonized["family_history"] = np.nan
    harmonized["diabetes_pedigree_function"] = compatible[
        "DiabetesPedigreeFunction"
    ]
    harmonized["age_years"] = compatible["Age"]
    harmonized["sex"] = "female"
    harmonized["race_ethnicity"] = "pima_indian_heritage"
    harmonized["serum_insulin_muu_ml"] = compatible["Insulin"].replace(0, np.nan)
    harmonized["insulin_measurement_type"] = "ogtt_2h"
    harmonized["skin_thickness_mm"] = compatible["SkinThickness"].replace(
        0, np.nan
    )
    harmonized["pregnancies"] = compatible["Pregnancies"]
    harmonized["waist_circumference_cm"] = np.nan
    harmonized["diabetes_outcome"] = compatible["Outcome"]
    harmonized["diabetes_outcome_definition"] = "pima_dataset_outcome"
    harmonized["fasting_sample_weight"] = np.nan
    harmonized["full_sample_mec_weight"] = np.nan
    harmonized["survey_psu"] = np.nan
    harmonized["survey_stratum"] = np.nan
    return harmonized[COMBINED_COLUMNS]


def _read_nhanes_file(path: Path, columns: list[str]) -> pd.DataFrame:
    """Lê somente colunas selecionadas de um arquivo XPT do NHANES."""
    dataframe = pd.read_sas(path, format="xport", encoding="utf-8")
    available = [column for column in columns if column in dataframe.columns]
    if "SEQN" not in available:
        raise ValueError(f"SEQN ausente no arquivo NHANES: {path}")
    return dataframe[available]


def prepare_nhanes(*, force: bool = False) -> pd.DataFrame:
    """Baixa módulos NHANES e retorna uma tabela harmonizada por participante."""
    nhanes_raw_dir = RAW_DIR / "nhanes_2017_2018"
    paths: dict[str, Path] = {}
    for component, file_name in NHANES_FILES.items():
        path = nhanes_raw_dir / f"{file_name}.xpt"
        download(f"{NHANES_BASE_URL}/{file_name}.xpt", path, force=force)
        paths[component] = path

    selected_columns = {
        "demographics": [
            "SEQN",
            "RIAGENDR",
            "RIDAGEYR",
            "RIDRETH3",
            "WTMEC2YR",
            "SDMVPSU",
            "SDMVSTRA",
        ],
        "body_measures": ["SEQN", "BMXBMI", "BMXWAIST"],
        "blood_pressure": [
            "SEQN",
            "BPXSY1",
            "BPXSY2",
            "BPXSY3",
            "BPXSY4",
            "BPXDI1",
            "BPXDI2",
            "BPXDI3",
            "BPXDI4",
        ],
        "fasting_glucose": ["SEQN", "LBXGLU", "WTSAF2YR"],
        "glycohemoglobin": ["SEQN", "LBXGH"],
        "total_cholesterol": ["SEQN", "LBXTC"],
        "triglycerides": ["SEQN", "LBXTR"],
        "insulin": ["SEQN", "LBXIN"],
        "diabetes_questionnaire": ["SEQN", "DIQ010", "DIQ175A"],
    }

    dataframes = {
        component: _read_nhanes_file(paths[component], columns)
        for component, columns in selected_columns.items()
    }
    merged = dataframes.pop("demographics")
    for dataframe in dataframes.values():
        merged = merged.merge(dataframe, on="SEQN", how="left", validate="one_to_one")

    systolic_columns = [f"BPXSY{number}" for number in range(1, 5)]
    diastolic_columns = [f"BPXDI{number}" for number in range(1, 5)]
    harmonized = pd.DataFrame(index=merged.index)
    harmonized["source_dataset"] = "nhanes_2017_2018"
    harmonized["participant_id"] = merged["SEQN"].astype("Int64").map(
        lambda value: f"nhanes_{value}"
    )
    harmonized["glucose_mg_dl"] = merged["LBXGLU"]
    harmonized["glucose_measurement_type"] = "fasting"
    harmonized["hba1c_percent"] = merged["LBXGH"]
    harmonized["bmi_kg_m2"] = merged["BMXBMI"]
    harmonized["systolic_bp_mmhg"] = merged[systolic_columns].mean(axis=1)
    harmonized["diastolic_bp_mmhg"] = merged[diastolic_columns].mean(axis=1)
    harmonized["total_cholesterol_mg_dl"] = merged["LBXTC"]
    harmonized["triglycerides_mg_dl"] = merged["LBXTR"]
    harmonized["family_history"] = merged["DIQ175A"].map({10.0: 1})
    harmonized["diabetes_pedigree_function"] = np.nan
    harmonized["age_years"] = merged["RIDAGEYR"]
    harmonized["sex"] = merged["RIAGENDR"].map({1.0: "male", 2.0: "female"})
    harmonized["race_ethnicity"] = merged["RIDRETH3"].map(
        {
            1.0: "mexican_american",
            2.0: "other_hispanic",
            3.0: "non_hispanic_white",
            4.0: "non_hispanic_black",
            6.0: "non_hispanic_asian",
            7.0: "other_or_multiracial",
        }
    )
    harmonized["serum_insulin_muu_ml"] = merged["LBXIN"]
    harmonized["insulin_measurement_type"] = "fasting"
    harmonized["skin_thickness_mm"] = np.nan
    harmonized["pregnancies"] = np.nan
    harmonized["waist_circumference_cm"] = merged["BMXWAIST"]
    harmonized["diabetes_outcome"] = merged["DIQ010"].map({1.0: 1, 2.0: 0})
    harmonized["diabetes_outcome_definition"] = "doctor_diagnosed_self_report"
    harmonized["fasting_sample_weight"] = merged["WTSAF2YR"]
    harmonized["full_sample_mec_weight"] = merged["WTMEC2YR"]
    harmonized["survey_psu"] = merged["SDMVPSU"]
    harmonized["survey_stratum"] = merged["SDMVSTRA"]
    return harmonized[COMBINED_COLUMNS]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Baixa e harmoniza Pima e NHANES 2017-2018."
    )
    parser.add_argument(
        "--force", action="store_true", help="Baixa novamente arquivos existentes."
    )
    args = parser.parse_args()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    pima = prepare_pima(force=args.force)
    nhanes = prepare_nhanes(force=args.force)
    combined = pd.concat([pima, nhanes], ignore_index=True)

    pima.to_csv(PROCESSED_DIR / "pima_diabetes.csv", index=False)
    nhanes.to_csv(PROCESSED_DIR / "nhanes_2017_2018.csv", index=False)
    combined.to_csv(PROJECT_ROOT / "healthai_dados_publicos.csv", index=False)

    print(f"Pima: {len(pima)} registros")
    print(f"NHANES 2017-2018: {len(nhanes)} registros")
    print(f"Combinado: {len(combined)} registros")


if __name__ == "__main__":
    main()
