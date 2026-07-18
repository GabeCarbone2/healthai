import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  RotateCcw,
} from "lucide-react";

import type { Experiment, Prediction } from "../types";

type Props = {
  experiment: Experiment;
  prediction: Prediction | null;
  onReset?: () => void;
};

export function ResultPanel({ experiment, prediction, onReset }: Props) {
  const probability = prediction ? Math.round(prediction.probability * 100) : 0;
  const threshold = prediction
    ? Math.round(prediction.decision_threshold * 100)
    : 50;
  const positive = prediction?.predicted_class === 1;
  const selectedMetrics = experiment.models[experiment.selected_model];
  const featureLabels = Object.fromEntries(
    experiment.input_fields.map((field) => [field.key, field.label]),
  );
  const importantFeatures =
    selectedMetrics?.explainability?.features.slice(0, 5) ?? [];
  const maxImportance = Math.max(
    ...importantFeatures.map((feature) => Math.max(feature.importance_mean, 0)),
    0.001,
  );
  const localFeatures = prediction?.local_explanation?.features ?? [];
  const maxLocalEffect = Math.max(
    ...localFeatures.map((feature) => Math.abs(feature.probability_effect)),
    0.001,
  );

  return (
    <aside className="result-panel" aria-live="polite" aria-labelledby="result-title">
      <div className="result-panel-heading">
        <div>
          <span className="page-eyebrow">Saída do modelo</span>
          <h2 id="result-title">Resultado</h2>
        </div>
        {prediction && onReset && (
          <button type="button" className="result-reset" onClick={onReset}>
            <RotateCcw size={15} aria-hidden="true" />
            Nova avaliação
          </button>
        )}
      </div>

      {prediction ? (
        <div className="result-content">
          <div className={`result-status ${positive ? "attention" : "neutral"}`}>
            {positive ? <AlertTriangle size={22} /> : <CheckCircle2 size={22} />}
            <div>
              <small>Interpretação pelo limiar configurado</small>
              <strong>
                {positive
                  ? "Acima do limiar do modelo"
                  : "Abaixo do limiar do modelo"}
              </strong>
            </div>
          </div>

          <div className="probability-readout">
            <span>Probabilidade estimada da classe do estudo</span>
            <strong>{probability}%</strong>
          </div>
          <progress
            className="probability-track"
            value={probability}
            max={100}
            aria-label="Probabilidade estimada da classe do estudo"
          >
            {probability}%
          </progress>
          <p className="threshold-note">
            O resultado muda de faixa a partir de {threshold}%; esse corte é
            configurado no modelo e não representa um diagnóstico.
          </p>

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
              <dt>Versão</dt>
              <dd><code>{prediction.model_version}</code></dd>
            </div>
            <div>
              <dt>Completude</dt>
              <dd>{Math.round(prediction.input_completeness * 100)}%</dd>
            </div>
          </dl>
          {prediction.missing_feature_count > 0 && (
            <p className="result-warning">
              <AlertTriangle size={17} aria-hidden="true" />
              <span>
                {prediction.missing_feature_count} medida(s) ausente(s) foram
                estimadas pelo pipeline. Revise este resultado com cautela.
              </span>
            </p>
          )}
          <p className="result-disclaimer">
            <strong>Predição gerada por modelo de aprendizado de máquina.</strong>
            <span>
              O HealthAI é uma ferramenta acadêmica de apoio à triagem. O
              resultado não substitui diagnóstico, avaliação clínica ou decisão
              médica.
            </span>
          </p>

          {localFeatures.length > 0 && (
            <details className="model-explanation local-explanation">
              <summary>Como este resultado foi calculado?</summary>
              <div>
                <h3>Influência nesta avaliação</h3>
                <ol>
                  {localFeatures.map((feature) => {
                    const effectPoints = Math.abs(feature.probability_effect * 100);
                    const direction = feature.direction === "increases"
                      ? "elevou"
                      : feature.direction === "decreases"
                        ? "reduziu"
                        : "não alterou";
                    return (
                      <li key={feature.feature}>
                        <div>
                          <span>{featureLabels[feature.feature] ?? feature.feature}</span>
                          <strong className={feature.direction}>
                            {direction} {effectPoints.toFixed(1)} p.p.
                          </strong>
                        </div>
                        <span className="importance-track" aria-hidden="true">
                          <span style={{ width: `${Math.max(3, (Math.abs(feature.probability_effect) / maxLocalEffect) * 100)}%` }} />
                        </span>
                      </li>
                    );
                  })}
                </ol>
                <p>{prediction.local_explanation?.interpretation}</p>
                <p>Calculada somente para esta resposta; os valores clínicos não são persistidos.</p>
              </div>
            </details>
          )}
        </div>
      ) : (
        <div className="result-empty">
          <ClipboardCheck size={34} aria-hidden="true" />
          <strong>Pronto para calcular</strong>
          <span>
            Preencha os campos obrigatórios. O resultado e sua rastreabilidade
            aparecerão aqui.
          </span>
        </div>
      )}

      {importantFeatures.length > 0 && (
        <details className="model-explanation global-explanation">
          <summary>Como o modelo se comporta globalmente?</summary>
          <div>
            <h3>Variáveis mais influentes no modelo</h3>
            <ol>
              {importantFeatures.map((feature) => (
                <li key={feature.feature}>
                  <div>
                    <span>{featureLabels[feature.feature] ?? feature.feature}</span>
                    <strong>
                      {feature.importance_mean > 0
                        ? feature.importance_mean.toFixed(3)
                        : "≈0"}
                    </strong>
                  </div>
                  <span className="importance-track" aria-hidden="true">
                    <span
                      style={{
                        width: `${Math.max(3, (Math.max(feature.importance_mean, 0) / maxImportance) * 100)}%`,
                      }}
                    />
                  </span>
                </li>
              ))}
            </ol>
            <p>
              Importância por permutação no teste global. Não explica esta
              avaliação individual, não indica causalidade e não deve ser usada
              isoladamente para decidir condutas.
            </p>
          </div>
        </details>
      )}
    </aside>
  );
}
