import { AlertTriangle, CheckCircle2 } from "lucide-react";

import type { Experiment, Prediction } from "../types";

type Props = {
  experiment: Experiment;
  prediction: Prediction | null;
};

export function ResultPanel({ experiment, prediction }: Props) {
  const probability = prediction ? Math.round(prediction.probability * 100) : 0;
  const threshold = prediction
    ? Math.round(prediction.decision_threshold * 100)
    : 50;
  const positive = prediction?.predicted_class === 1;

  return (
    <aside className="result-panel" aria-live="polite">
      <h2>Resultado</h2>

      {prediction ? (
        <div className="result-content">
          <div className={`result-status ${positive ? "attention" : "neutral"}`}>
            {positive ? <AlertTriangle size={22} /> : <CheckCircle2 size={22} />}
            <div>
              <strong>
                {positive
                  ? "Acima do limiar do modelo"
                  : "Abaixo do limiar do modelo"}
              </strong>
            </div>
          </div>

          <div className="probability-readout">
            <span>Probabilidade estimada</span>
            <strong>{probability}%</strong>
          </div>
          <div
            className="probability-track"
            role="progressbar"
            aria-valuenow={probability}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <span style={{ width: `${probability}%` }} />
          </div>

          <dl className="result-details">
            <div>
              <dt>Perfil</dt>
              <dd>{experiment.label}</dd>
            </div>
            <div>
              <dt>Modelo</dt>
              <dd>{experiment.selected_model_label}</dd>
            </div>
            <div>
              <dt>Limiar</dt>
              <dd>{threshold}%</dd>
            </div>
          </dl>
        </div>
      ) : (
        <div className="result-empty">
          <span>O resultado aparecerá após o cálculo.</span>
        </div>
      )}
    </aside>
  );
}
