import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  Info,
  RotateCcw,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { Experiment, Prediction } from "../types";
import { formatBrazilianDateTime } from "../utils/date";

type Props = {
  experiment: Experiment;
  prediction: Prediction | null;
  patientIdentifier?: string;
  performedAt?: string;
  estimatedFieldLabels?: string[];
  requiredProgress?: {
    completed: number;
    total: number;
  };
  onReset?: () => void;
};

type ConfidenceInterval = {
  lower: number;
  upper: number;
} | null | undefined;

function formatMetric(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value)
    ? `${Math.round(value * 100)}%`
    : "Não disponível";
}

function formatMetricWithConfidence(
  value: number | null | undefined,
  interval: ConfidenceInterval,
) {
  const metric = formatMetric(value);
  if (
    metric === "Não disponível"
    || !interval
    || !Number.isFinite(interval.lower)
    || !Number.isFinite(interval.upper)
  ) {
    return metric;
  }
  return `${metric} — IC 95%: ${formatMetric(interval.lower)} a ${formatMetric(interval.upper)}`;
}

function formatSignedPoints(value: number) {
  if (Math.abs(value) < 0.0005) return "0,0";
  const magnitude = new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(Math.abs(value) * 100);
  return `${value > 0 ? "+" : "−"}${magnitude}`;
}

function displayVersion(value: string) {
  return value && !/legacy|unknown|unversioned/i.test(value)
    ? value
    : "Não registrada";
}

export function ResultPanel({
  experiment,
  prediction,
  patientIdentifier,
  performedAt,
  estimatedFieldLabels = [],
  requiredProgress,
  onReset,
}: Props) {
  const [informationOpen, setInformationOpen] = useState(false);
  const [localExplanationOpen, setLocalExplanationOpen] = useState(false);
  const [technicalDetailsOpen, setTechnicalDetailsOpen] = useState(false);
  const probability = prediction ? Math.round(prediction.probability * 100) : 0;
  const attentionReference = prediction
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
  const featureLabels = useMemo(
    () => Object.fromEntries(
      experiment.input_fields.map((field) => [
        field.key,
        field.key === "diabetes_pedigree_function"
          ? "Índice de histórico familiar"
          : field.label,
      ]),
    ),
    [experiment.input_fields],
  );
  const estimatedLabels = useMemo(
    () => new Set(estimatedFieldLabels),
    [estimatedFieldLabels],
  );
  const importantFeatures =
    selectedMetrics?.explainability?.features.slice(0, 5) ?? [];
  const maxImportance = Math.max(
    ...importantFeatures.map((feature) => Math.max(feature.importance_mean, 0)),
    0.001,
  );
  const localFeatures = prediction?.local_explanation?.features ?? [];
  const confidenceIntervals = selectedMetrics?.confidence_intervals?.metrics;

  useEffect(() => {
    setInformationOpen(false);
    setLocalExplanationOpen(false);
    setTechnicalDetailsOpen(false);
  }, [experiment.id, prediction]);

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

          <section
            className={`result-measure ${positive ? "attention" : "neutral"}`}
            aria-labelledby="probability-label"
          >
            <div className="result-measure-values">
              <div className="probability-readout">
                <span id="probability-label">Probabilidade estimada</span>
                <strong>{probability}%</strong>
              </div>
              <div className="attention-reference-readout">
                <span>Referência de atenção utilizada</span>
                <strong>{attentionReference}%</strong>
              </div>
            </div>
            <div
              className="probability-scale"
              role="img"
              aria-label={`Probabilidade estimada de ${probability}%, referência de atenção de ${attentionReference}% e classificação ${positive ? "acima" : "abaixo"} do nível de atenção.`}
            >
              <progress
                className={`probability-track ${positive ? "attention" : "neutral"}`}
                value={probability}
                max={100}
                aria-label="Probabilidade estimada de risco"
              >
                {probability}%
              </progress>
              <span
                className="attention-reference-marker"
                style={{ left: `${attentionReference}%` }}
                aria-hidden="true"
              />
              <span className="probability-scale-start" aria-hidden="true">0%</span>
              <span
                className="attention-reference-label"
                style={{ left: `${attentionReference}%` }}
                aria-hidden="true"
              >
                referência
              </span>
              <span className="probability-scale-end" aria-hidden="true">100%</span>
            </div>
            <p className="attention-reference-help">
              <Info size={15} aria-hidden="true" />
              A classificação é obtida comparando a probabilidade calculada com
              a referência de atenção definida para esta versão da análise. Essa
              referência não é um valor diagnóstico.
            </p>
          </section>

          <section className={`result-interpretation ${positive ? "attention" : "information"}`}>
            <h3>Interpretação</h3>
            <p>
              {positive
                ? "A estimativa ficou acima da referência de atenção utilizada pelo HealthAI. Considere avaliação clínica complementar, histórico, exames, sintomas, condições associadas e demais informações do paciente antes de qualquer decisão."
                : "A estimativa ficou abaixo da referência de atenção utilizada pelo HealthAI. Considere histórico, exames, sintomas, condições associadas e julgamento clínico antes de qualquer decisão."}
            </p>
          </section>

          <section className="result-section result-quality" aria-labelledby="quality-title">
            <h3 id="quality-title">Qualidade das informações</h3>
            <dl>
              <div>
                <dt>Completude</dt>
                <dd>{completedFields} de {totalFields} campos informados</dd>
              </div>
              <div>
                <dt>Dados estimados</dt>
                <dd>
                  {prediction.missing_feature_count === 0
                    ? "Nenhum campo"
                    : `${prediction.missing_feature_count} ${prediction.missing_feature_count === 1 ? "campo" : "campos"}`}
                </dd>
              </div>
            </dl>
          </section>

          <section
            className={`result-section missing-data-section ${prediction.missing_feature_count > 0 ? "attention" : "complete"}`}
            aria-labelledby="missing-data-title"
          >
            <h3 id="missing-data-title">
              {prediction.missing_feature_count > 0
                ? <AlertTriangle size={17} aria-hidden="true" />
                : <CheckCircle2 size={17} aria-hidden="true" />}
              Dados ausentes ou estimados
            </h3>
            {prediction.missing_feature_count === 0 ? (
              <p>Nenhum campo foi estimado estatisticamente.</p>
            ) : (
              <>
                <p>
                  {prediction.missing_feature_count}{" "}
                  {prediction.missing_feature_count === 1
                    ? "campo foi substituído"
                    : "campos foram substituídos"}{" "}
                  por {prediction.missing_feature_count === 1
                    ? "uma referência estatística"
                    : "referências estatísticas"}:
                </p>
                {estimatedFieldLabels.length > 0 && (
                  <ul>
                    {estimatedFieldLabels.map((label) => (
                      <li key={label}>{label}</li>
                    ))}
                  </ul>
                )}
                <p>
                  Informações substituídas por referências estatísticas podem
                  reduzir a confiabilidade desta avaliação.
                </p>
              </>
            )}
          </section>

          <section className="result-disclaimer">
            <h3>Limitação de uso</h3>
            <p>
              O resultado é uma estimativa de apoio à triagem e não representa
              diagnóstico médico. Não substitui exames, avaliação médica ou
              julgamento clínico.
            </p>
          </section>

          <section className="result-section assessment-metadata" aria-labelledby="assessment-data-title">
            <h3 id="assessment-data-title">Dados da avaliação</h3>
            <dl>
              {patientIdentifier && (
                <div><dt>Identificador</dt><dd>{patientIdentifier}</dd></div>
              )}
              <div><dt>Perfil</dt><dd>{profileLabel}</dd></div>
              {performedAt && (
                <div><dt>Realizada em</dt><dd>{formatBrazilianDateTime(performedAt)}</dd></div>
              )}
              <div><dt>Completude</dt><dd>{completedFields} de {totalFields} campos</dd></div>
              <div><dt>Versão da análise</dt><dd>{displayVersion(prediction.model_version)}</dd></div>
            </dl>
          </section>

          <details
            className="model-explanation assessment-information"
            open={informationOpen}
            onToggle={(event) => setInformationOpen(event.currentTarget.open)}
          >
            <summary aria-expanded={informationOpen}>
              Informações consideradas
            </summary>
            <div>
              <p>
                A avaliação considerou os campos abaixo. Os valores clínicos
                utilizados no cálculo não são persistidos no histórico.
              </p>
              <ul className="considered-information-list">
                {experiment.input_fields.map((field) => {
                  const label = featureLabels[field.key] ?? field.label;
                  return (
                    <li key={field.key}>
                      <span>{label}</span>
                      <strong>
                        {estimatedLabels.has(label)
                          ? "Referência estatística"
                          : "Informado"}
                      </strong>
                    </li>
                  );
                })}
              </ul>
            </div>
          </details>

          <details
            className="model-explanation technical-evaluation-details"
            open={technicalDetailsOpen}
            onToggle={(event) => setTechnicalDetailsOpen(event.currentTarget.open)}
          >
            <summary aria-expanded={technicalDetailsOpen}>
              Transparência técnica da avaliação
            </summary>
            <div>
              <p className="technical-context-note">
                Essas informações descrevem o funcionamento técnico geral da
                análise e não substituem a interpretação clínica individual.
              </p>

              <section className="technical-section">
                <h3>Identificação da análise</h3>
                <dl className="result-details" aria-label="Rastreabilidade técnica">
                  <div><dt>Base utilizada</dt><dd>{technicalBase}{experiment.source_dataset ? ` · ${experiment.source_dataset}` : ""}</dd></div>
                  <div><dt>Algoritmo utilizado</dt><dd>{experiment.selected_model_label}</dd></div>
                  <div><dt>Versão da análise</dt><dd><code>{displayVersion(prediction.model_version)}</code></dd></div>
                  <div><dt>Referência de atenção</dt><dd>{attentionReference}%</dd></div>
                  {Number.isFinite(experiment.n_train) && Number.isFinite(experiment.n_test) && (
                    <div><dt>Registros de desenvolvimento</dt><dd>{experiment.n_train} treino · {experiment.n_test} teste</dd></div>
                  )}
                </dl>
              </section>

              {selectedMetrics && (
                <section className="technical-section">
                  <h3>Desempenho na avaliação interna</h3>
                  <dl className="technical-metrics" aria-label="Métricas da avaliação interna">
                    <div>
                      <dt>Sensibilidade</dt>
                      <dd>{formatMetricWithConfidence(selectedMetrics.recall, confidenceIntervals?.recall)}</dd>
                    </div>
                    <div>
                      <dt>F1-score</dt>
                      <dd>{formatMetricWithConfidence(selectedMetrics.f1, confidenceIntervals?.f1)}</dd>
                    </div>
                    <div>
                      <dt>AUC-ROC</dt>
                      <dd>{formatMetricWithConfidence(selectedMetrics.roc_auc, confidenceIntervals?.roc_auc)}</dd>
                    </div>
                  </dl>
                  <p>
                    Métricas obtidas em uma avaliação interna da base de
                    desenvolvimento. Não representam validação externa e não
                    garantem o mesmo desempenho em outros serviços, pacientes ou
                    populações.
                  </p>
                </section>
              )}

              <section className="technical-section">
                <h3>Limitações metodológicas</h3>
                <p>
                  A avaliação foi realizada internamente na base de origem, sem
                  validação externa. A referência de atenção organiza a
                  classificação desta triagem e não representa diagnóstico.
                </p>
              </section>

              {localFeatures.length > 0 && (
                <details
                  className="technical-sensitivity"
                  open={localExplanationOpen}
                  onToggle={(event) => setLocalExplanationOpen(event.currentTarget.open)}
                >
                  <summary aria-expanded={localExplanationOpen}>
                    Análise técnica de sensibilidade
                  </summary>
                  <div>
                    <p>
                      Esta análise mostra como a probabilidade calculada muda
                      quando cada informação é substituída individualmente por
                      uma referência estatística. Os efeitos não são causais nem
                      aditivos.
                    </p>
                    <p>
                      Essa diferença representa uma nova execução técnica e não
                      um efeito causal da variável.
                    </p>
                    <ol className="sensitivity-list">
                      {localFeatures.map((feature) => {
                        const referenceProbability = Math.min(
                          1,
                          Math.max(
                            0,
                            prediction.probability - feature.probability_effect,
                          ),
                        );
                        return (
                          <li key={feature.feature}>
                            <h4>{featureLabels[feature.feature] ?? feature.feature}</h4>
                            <dl>
                              <div>
                                <dt>Probabilidade original</dt>
                                <dd>{formatMetric(prediction.probability)}</dd>
                              </div>
                              <div>
                                <dt>Probabilidade com valor de referência</dt>
                                <dd>{formatMetric(referenceProbability)}</dd>
                              </div>
                              <div>
                                <dt>Diferença na análise de referência</dt>
                                <dd>{formatSignedPoints(feature.probability_effect)} pontos percentuais</dd>
                              </div>
                            </dl>
                          </li>
                        );
                      })}
                    </ol>
                  </div>
                </details>
              )}

              {importantFeatures.length > 0 && (
                <section className="technical-feature-list" aria-labelledby="global-factors-title">
                  <h3 id="global-factors-title">Informações com maior influência geral no sistema</h3>
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
                    Esses valores representam o comportamento geral da análise no
                    conjunto avaliado. Não explicam individualmente esta avaliação
                    e não representam relações causais.
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
          {requiredProgress && (
            <small>
              Campos obrigatórios preenchidos:{" "}
              <strong>{requiredProgress.completed} de {requiredProgress.total}</strong>
            </small>
          )}
        </div>
      )}
    </aside>
  );
}
