import numpy as np

from healthai.features import build_baseline_pipeline


def test_baseline_pipeline_handles_missing_values() -> None:
    x = np.array([[80.0, 20.0], [120.0, np.nan], [160.0, 35.0], [190.0, 40.0]])
    y = np.array([0, 0, 1, 1])
    pipeline = build_baseline_pipeline()

    pipeline.fit(x, y)

    assert pipeline.predict([[130.0, np.nan]]).shape == (1,)
