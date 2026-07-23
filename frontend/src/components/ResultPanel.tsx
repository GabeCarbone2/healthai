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

function formatMetric(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value)
    ? `${Math.round(value * 100)}%`
    : "Não disponível";
}

export function ResultPanel({ experiment, prediction, onReset }: Props) {
  const [localExplanationOpen, setLocalExplanationOpen] = useState(false);
  const [technicalDetailsOpen, setTechnicalDetailsOpen] = useState(false);
  const probability = prediction ? Math.round(prediction.probability * 100) : 0;
  const threshold = prediction
    ? Math.round(prediction.decision_threshold * 100)
    : 50;
  const positive = prediction?.predicted_class === 1;
  const profileLabel = experiment.id === "pima" ? "Mulher adulta" : "Adulto";
  const technicalBase = experiment.id === "pima" ? "Pima" : "NHANES";
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
    setTechnicalDetailsOpen(false);
  }, [experiment.id]);

  useEffect(() => {
    setLocalExplanationOpen(false);
  }, [prediction]);

  return (
    <aside className="result-panel" aria-live="polite" aria-labelledby="result-title">
      <div className="result-panel-heading">
        <div>
          <span className="page-eyebrow">Apoio à interpretação</span>
          <h2 id="result-title">Resultado da triagem</h2>
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
                  ? "Acima do nível de atenção"
                  : "Abaixo do nível de atenção"}
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
              aria-label="Probabilidade estimada de risco"
            >
              {probability}%
            </progress>
          </section>

          <dl className="result-summary clinical-result-summary">
            <div className={`result-guidance ${positive ? "attention" : "information"}`}>
              <dt>Interpretação</dt>
              <dd>
                {positive
                  ? "Os dados informados sugerem necessidade de avaliação clínica complementar. Considere histórico, exames e demais condições do paciente antes de qualquer decisão."
                  : "A estimativa ficou abaixo do nível de atenção. Considere histórico, exames, demais condições do paciente e julgamento clínico na avaliação."}
              </dd>
            </div>
            <div className="result-completeness">
              <dt>Completude dos dados</dt>
              <dd>{completedFields} de {totalFields} campos informados</dd>
              <small>
                {prediction.missing_feature_count === 0
                  ? "Nenhum campo estimado estatisticamente."
                  : `${prediction.missing_feature_count} ${prediction.missing_feature_count === 1 ? "campo estimado" : "campos estimados"} estatisticamente.`}
              </small>
            </div>
          </dl>

          {prediction.missing_feature_count > 0 && (
            <p className="result-warning">
              <AlertTriangle size={17} aria-hidden="true" />
              <span>
                {prediction.missing_feature_count} {prediction.missing_feature_count === 1 ? "campo foi estimado" : "campos foram estimados"} estatisticamente.
                Isso pode reduzir a confiabilidade desta avaliação.
              </span>
            </p>
          )}
          <p className="result-disclaimer">
            <strong>Limitação de uso</strong>
            <span>
              O resultado é uma estimativa de apoio à triagem e não representa
              diagnóstico médico. Não substitui exames, avaliação médica ou
              julgamento clínico.
            </span>
          </p>

          {localFeatures.length > 0 && (
            <details
              className="model-explanation local-explanation"
              open={localExplanationOpen}
              onToggle={(event) => setLocalExplanationOpen(event.currentTarget.open)}
            >
              <summary aria-expanded={localExplanationOpen}>
                Informações consideradas nesta avaliação
              </summary>
              <div>
                <h3>Variações estimadas nesta avaliação</h3>
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
                <p>
                  Estas variações são não causais e não aditivas. Elas não
                  demonstram que um fator específico causou o resultado.
                </p>
                <p>Calculadas somente para esta resposta; os valores clínicos não são persistidos.</p>
              </div>
            </details>
          )}

          <details
            className="model-explanation technical-evaluation-details"
            open={technicalDetailsOpen}
            onToggle={(event) => setTechnicalDetailsOpen(event.currentTarget.open)}
          >
            <summary aria-expanded={technicalDetailsOpen}>
              Detalhes técnicos da avaliação
            </summary>
            <div>
              <p className="technical-context-note">
                Estas informações descrevem o funcionamento técnico geral e não
                substituem a interpretação clínica individual.
              </p>
              <dl className="result-details" aria-label="Rastreabilidade técnica">
                <div><dt>Perfil da avaliação</dt><dd>{profileLabel}</dd></div>
                <div>
                  <dt>Base utilizada</dt>
                  <dd>{technicalBase}{experiment.source_dataset ? ` · ${experiment.source_dataset}` : ""}</dd>
                </div>
                <div><dt>Algoritmo utilizado</dt><dd>{experiment.selected_model_label}</dd></div>
                <div><dt>Versão da análise</dt><dd><code>{prediction.model_version}</code></dd></div>
                <div><dt>Limiar</dt><dd>{threshold}%</dd></div>
                {Number.isFinite(experiment.n_train) && Number.isFinite(experiment.n_test) && (
                  <div><dt>Registros de desenvolvimento</dt><dd>{experiment.n_train} treino · {experiment.n_test} teste</dd></div>
                )}
              </dl>
              {selectedMetrics && (
                <dl className="technical-metrics" aria-label="Métricas globais da análise">
                  <div><dt>Recall</dt><dd>{formatMetric(selectedMetrics.recall)}</dd></div>
                  <div><dt>F1-score</dt><dd>{formatMetric(selectedMetrics.f1)}</dd></div>
                  <div><dt>AUC-ROC</dt><dd>{formatMetric(selectedMetrics.roc_auc)}</dd></div>
                </dl>
              )}
              <p>
                Limitação metodológica: avaliação interna na base de origem, sem
                validação externa. O limiar organiza a faixa de atenção e não
                representa diagnóstico.
              </p>

              {importantFeatures.length > 0 && (
                <section className="technical-feature-list" aria-labelledby="global-factors-title">
                  <h3 id="global-factors-title">Fatores mais considerados pelo sistema</h3>
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
                    Esses fatores descrevem o comportamento geral da análise e
                    não explicam individualmente este resultado. Não indicam
                    causalidade e não devem ser usados isoladamente para decidir
                    condutas.
                  </p>
                </section>
              )}
            </div>
          </details>
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

    </aside>
  );
}
