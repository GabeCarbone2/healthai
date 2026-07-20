import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  RotateCcw,
} from "lucide-react";
import { useEffect, useState } from "react";

import type { Experiment, Prediction } from "../types";

type Props = {
  experiment: Experiment;
  prediction: Prediction | null;
  onReset?: () => void;
};

export function ResultPanel({ experiment, prediction, onReset }: Props) {
  const [localExplanationOpen, setLocalExplanationOpen] = useState(false);
  const [globalExplanationOpen, setGlobalExplanationOpen] = useState(false);
  const probability = prediction ? Math.round(prediction.probability * 100) : 0;
  const threshold = prediction
    ? Math.round(prediction.decision_threshold * 100)
    : 50;
  const positive = prediction?.predicted_class === 1;
  const totalFields = experiment.input_fields.length;
  const completedFields = prediction
    ? Math.max(0, totalFields - prediction.missing_feature_count)
    : 0;
  const selectedMetrics = experiment.models[experiment.selected_model];
  const featureLabels = Object.fromEntries(
    experiment.input_fields.map((field) => [
      field.key,
      field.key === "diabetes_pedigree_function"
        ? "Índice de histórico familiar"
        : field.label,
    ]),
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

  useEffect(() => {
    setGlobalExplanationOpen(false);
  }, [experiment.id]);

  useEffect(() => {
    setLocalExplanationOpen(false);
  }, [prediction]);

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
            {positive
              ? <AlertTriangle size={22} aria-hidden="true" />
              : <CheckCircle2 size={22} aria-hidden="true" />}
            <div>
              <small>Classificação da triagem</small>
              <strong>
                {positive
                  ? "Acima do limiar"
                  : "Abaixo do limiar"}
              </strong>
            </div>
          </div>

          <section className="result-measure" aria-labelledby="probability-label">
            <div className="probability-readout">
              <span id="probability-label">Probabilidade estimada</span>
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
          </section>

          <dl className="result-summary">
            <div>
              <dt>Limiar utilizado</dt>
              <dd>{threshold}%</dd>
              <small>Define a mudança de faixa e não representa diagnóstico.</small>
            </div>
            <div>
              <dt>Completude dos dados</dt>
              <dd>{completedFields} de {totalFields} campos informados</dd>
              <small>
                {prediction.missing_feature_count === 0
                  ? "Nenhum campo estimado estatisticamente."
                  : `${prediction.missing_feature_count} ${prediction.missing_feature_count === 1 ? "campo estimado" : "campos estimados"} estatisticamente.`}
              </small>
            </div>
            <div className={`result-guidance ${positive ? "attention" : "information"}`}>
              <dt>Orientação de interpretação</dt>
              <dd>
                {positive
                  ? "O resultado sugere necessidade de avaliação clínica complementar."
                  : "O resultado ficou abaixo do limiar, mas deve ser interpretado junto à avaliação clínica."}
              </dd>
            </div>
          </dl>

          <dl className="result-details" aria-label="Rastreabilidade técnica">
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
          </dl>
          {prediction.missing_feature_count > 0 && (
            <p className="result-warning">
              <AlertTriangle size={17} aria-hidden="true" />
              <span>
                Há {prediction.missing_feature_count} {prediction.missing_feature_count === 1 ? "campo ausente" : "campos ausentes"}.
                O modelo utilizou estimativas estatísticas, o que pode reduzir a
                confiabilidade desta avaliação.
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
            <details
              className="model-explanation local-explanation"
              open={localExplanationOpen}
              onToggle={(event) => setLocalExplanationOpen(event.currentTarget.open)}
            >
              <summary aria-expanded={localExplanationOpen}>
                Como este resultado foi calculado?
              </summary>
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
            Preencha os campos obrigatórios para gerar a avaliação.
          </span>
        </div>
      )}

      {importantFeatures.length > 0 && (
        <details
          className="model-explanation global-explanation"
          open={globalExplanationOpen}
          onToggle={(event) => setGlobalExplanationOpen(event.currentTarget.open)}
        >
          <summary aria-expanded={globalExplanationOpen}>
            Como o modelo se comporta globalmente?
          </summary>
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
              Esses valores descrevem o comportamento geral do modelo e não explicam
              individualmente esta avaliação. A importância por permutação não indica
              causalidade e não deve ser usada isoladamente para decidir condutas.
            </p>
          </div>
        </details>
      )}
    </aside>
  );
}
