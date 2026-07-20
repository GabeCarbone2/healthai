import {
  Activity,
  ArrowRight,
  Check,
  Clipboard,
  Info,
  RotateCcw,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { createPrediction } from "../api";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { ErrorSummary } from "../components/ErrorSummary";
import { ResultPanel } from "../components/ResultPanel";
import type { Experiment, InputField, PatientResult, Prediction } from "../types";

type Props = {
  experiments: Experiment[];
  onResult: (result: PatientResult) => void;
};

const PRESENTATION = {
  pima: {
    title: "Pima — mulheres adultas",
    short: "Mulheres adultas",
    description: "Base Pima",
    population: "mulheres adultas representadas na base Pima",
  },
  nhanes: {
    title: "NHANES — adultos",
    short: "Adultos",
    description: "Base NHANES",
    population: "adultos representados na base NHANES",
  },
} as const;

const FIELD_HELP: Record<string, string> = {
  pregnancies: "Número de gestações informadas.",
  diabetes_pedigree_function:
    "Diabetes Pedigree Function, variável utilizada pela base Pima.",
  skin_thickness_mm:
    "Refere-se à espessura da prega cutânea do tríceps, em milímetros.",
  serum_insulin_muu_ml:
    "Concentração de insulina sérica na unidade indicada.",
};

const FIELD_LABELS: Record<string, string> = {
  diabetes_pedigree_function: "Índice de histórico familiar",
};

const OPTIONAL_FIELDS_NOTE =
  "Campos opcionais podem ser estimados estatisticamente quando não informados. Isso pode reduzir a confiabilidade da avaliação.";

type FieldTooltipProps = {
  id: string;
  label: string;
  text: string;
};

function FieldTooltip({ id, label, text }: FieldTooltipProps) {
  return (
    <span className="field-tooltip">
      <button
        type="button"
        aria-label={`Ajuda sobre ${label}`}
        aria-describedby={id}
      >
        <Info size={14} aria-hidden="true" />
      </button>
      <span className="field-tooltip-content" id={id} role="tooltip">
        {text}
      </span>
    </span>
  );
}

function createPatientIdentifier() {
  const randomPart = crypto.randomUUID().replaceAll("-", "").slice(0, 12);
  return `PAC-${randomPart.toUpperCase()}`;
}

function createEmptyValues(fields: InputField[]) {
  return Object.fromEntries(fields.map((field) => [field.key, ""]));
}

function parseDecimal(value: string) {
  return Number(value.trim().replace(",", "."));
}

function formatClinicalNumber(value: number) {
  return new Intl.NumberFormat("pt-BR", {
    maximumFractionDigits: 3,
    useGrouping: false,
  }).format(value);
}

function validateField(field: InputField, value: string) {
  if (!value.trim()) return field.required ? "Preencha este campo." : "";
  if (field.type === "select") return "";

  const number = parseDecimal(value);
  if (!Number.isFinite(number)) return "Informe um número válido.";
  if (field.min !== undefined && number < field.min) {
    return `O valor mínimo permitido é ${formatClinicalNumber(field.min)}.`;
  }
  if (field.max !== undefined && number > field.max) {
    return `O valor máximo permitido é ${formatClinicalNumber(field.max)}.`;
  }
  if (field.step === 1 && !Number.isInteger(number)) {
    return "Informe um número inteiro.";
  }
  return "";
}

export function Assessment({ experiments, onResult }: Props) {
  const [experimentId, setExperimentId] = useState(experiments[0]?.id);
  const [patientIdentifier, setPatientIdentifier] = useState(
    createPatientIdentifier,
  );
  const [values, setValues] = useState<Record<string, string>>(() =>
    createEmptyValues(experiments[0]?.input_fields ?? []),
  );
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [confirmingClear, setConfirmingClear] = useState(false);
  const [patientIdentifierError, setPatientIdentifierError] = useState("");
  const [profileDetailsOpen, setProfileDetailsOpen] = useState(false);
  const errorRef = useRef<HTMLDivElement>(null);
  const submittingRef = useRef(false);
  const experiment = useMemo(
    () =>
      experiments.find((item) => item.id === experimentId) ?? experiments[0],
    [experimentId, experiments],
  );

  useEffect(() => {
    const selectedExperiment = experiments.find((item) => item.id === experimentId);
    setValues(createEmptyValues(selectedExperiment?.input_fields ?? []));
    setFieldErrors({});
    setPatientIdentifier(createPatientIdentifier());
    setPrediction(null);
    setError("");
    setCopied(false);
    setConfirmingClear(false);
    setPatientIdentifierError("");
    setProfileDetailsOpen(false);
  }, [experimentId, experiments]);

  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  if (!experiment) return null;

  const presentation = PRESENTATION[experiment.id];
  const requiredFields = experiment.input_fields.filter((field) => field.required);
  const completedRequiredFields = requiredFields.filter(
    (field) => Boolean(values[field.key]?.trim()),
  ).length;
  const allRequiredFieldsCompleted =
    completedRequiredFields === requiredFields.length;
  const hasEnteredValues = Object.values(values).some((value) => value.trim());

  function validatePatientIdentifier(value: string) {
    return /^PAC-[A-Z0-9]{8,20}$/.test(value)
      ? ""
      : "Use um identificador no formato PAC- seguido de 8 a 20 letras ou números.";
  }

  function updateValue(field: InputField, value: string) {
    setValues((current) => ({ ...current, [field.key]: value }));
    setFieldErrors((current) => ({
      ...current,
      [field.key]: current[field.key] ? validateField(field, value) : "",
    }));
    setPrediction(null);
    setError("");
  }

  async function copyIdentifier() {
    try {
      await navigator.clipboard.writeText(patientIdentifier);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setError("Não foi possível copiar o identificador neste navegador.");
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (submittingRef.current || loading) return;
    const nextErrors = Object.fromEntries(
      experiment.input_fields.map((field) => [
        field.key,
        validateField(field, values[field.key] ?? ""),
      ]),
    );
    setFieldErrors(nextErrors);
    const nextPatientIdentifierError = validatePatientIdentifier(patientIdentifier);
    setPatientIdentifierError(nextPatientIdentifierError);
    if (Object.values(nextErrors).some(Boolean) || nextPatientIdentifierError) {
      setError("Há campos ausentes ou com valores fora do intervalo permitido.");
      return;
    }

    if (experiment.id === "nhanes") {
      const clinicalMeasurementKeys = [
        "bmi_kg_m2",
        "systolic_bp_mmhg",
        "diastolic_bp_mmhg",
        "hba1c_percent",
        "glucose_mg_dl",
      ];
      const completedMeasurements = clinicalMeasurementKeys.filter(
        (key) => Boolean(values[key]?.trim()),
      ).length;
      if (completedMeasurements < 3) {
        setError("Informe ao menos três das cinco medidas clínicas do perfil NHANES.");
        return;
      }
      const systolic = values.systolic_bp_mmhg?.trim();
      const diastolic = values.diastolic_bp_mmhg?.trim();
      if (systolic && diastolic && parseDecimal(systolic) <= parseDecimal(diastolic)) {
        setFieldErrors((current) => ({
          ...current,
          diastolic_bp_mmhg:
            "A pressão diastólica deve ser menor que a pressão sistólica.",
        }));
        setError("Revise os valores de pressão arterial informados.");
        return;
      }
    }

    submittingRef.current = true;
    setLoading(true);
    setError("");
    const payload = Object.fromEntries(
      experiment.input_fields.map((field) => {
        const value = values[field.key]?.trim();
        if (!value) return [field.key, null];
        return [
          field.key,
          field.type === "number" ? parseDecimal(value) : value,
        ];
      }),
    );
    try {
      const savedResult = await createPrediction(
        experiment.id,
        payload,
        patientIdentifier,
      );
      setPrediction({
        experiment: savedResult.experiment,
        model: savedResult.model,
        model_version: savedResult.modelVersion,
        predicted_class: savedResult.predictedClass,
        probability: savedResult.probability,
        decision_threshold: savedResult.decisionThreshold,
        input_completeness: savedResult.inputCompleteness,
        missing_feature_count: savedResult.missingFeatureCount,
        local_explanation: savedResult.localExplanation,
      });
      onResult(savedResult);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível calcular a previsão.",
      );
    } finally {
      submittingRef.current = false;
      setLoading(false);
    }
  }

  function resetForm() {
    setValues(createEmptyValues(experiment.input_fields));
    setFieldErrors({});
    setPatientIdentifier(createPatientIdentifier());
    setPrediction(null);
    setError("");
    setCopied(false);
    setPatientIdentifierError("");
    setConfirmingClear(false);
  }

  function requestClear() {
    if (hasEnteredValues) {
      setConfirmingClear(true);
      return;
    }
    resetForm();
  }

  return (
    <div className="page assessment-page">
      <header className="page-header assessment-header">
        <div>
          <span className="page-eyebrow">Apoio acadêmico à decisão</span>
          <h1>Nova avaliação</h1>
          <p>Preencha as medidas disponíveis e revise antes de calcular.</p>
        </div>
        <div className="model-selector">
          <span>Selecione o perfil do modelo</span>
          <div className="model-switch" aria-label="Perfil do modelo">
            {experiments.map((item) => {
              const selected = item.id === experiment.id;
              return (
                <button
                  key={item.id}
                  className={selected ? "active" : ""}
                  aria-pressed={selected}
                  type="button"
                  onClick={() => setExperimentId(item.id)}
                >
                  <strong>{PRESENTATION[item.id].title}</strong>
                  <small>{PRESENTATION[item.id].description}</small>
                  {selected && (
                    <span className="model-selected">
                      <Check size={13} aria-hidden="true" />
                      Selecionado
                    </span>
                  )}
                </button>
              );
            })}
          </div>
          <p className="model-current">
            Modelo atual: <strong>{experiment.selected_model_label}</strong> · {presentation.short.toLowerCase()}
          </p>
        </div>
      </header>

      <details
        className="model-context"
        open={profileDetailsOpen}
        onToggle={(event) => setProfileDetailsOpen(event.currentTarget.open)}
      >
        <summary aria-expanded={profileDetailsOpen}>
          <Info size={16} aria-hidden="true" />
          Sobre este perfil e suas limitações
        </summary>
        <div>
          <p>
            <strong>{presentation.title}</strong> foi treinado para a população de {presentation.population},
            com {experiment.n_train} registros de treino e {experiment.n_test} de teste
            da base {experiment.source_dataset}.
          </p>
          <p>
            Modelo utilizado: {experiment.selected_model_label}. A população e os
            intervalos observados nessa base limitam a generalização para outros grupos.
            O uso é acadêmico e os resultados não equivalem a diagnóstico, risco futuro
            validado ou recomendação clínica.
          </p>
          <p>
            Campos opcionais ausentes podem ser estimados estatisticamente pelo modelo,
            com possível redução da confiabilidade da avaliação.
          </p>
        </div>
      </details>

      <div className="assessment-layout">
        <section className="form-section" aria-labelledby="patient-data-title">
          <div className="section-heading">
            <div>
              <h2 id="patient-data-title">Informações do paciente</h2>
              <p>{presentation.short} · {experiment.selected_model_label}</p>
            </div>
          </div>

          <p className="optional-fields-note" role="note">
            <Info size={16} aria-hidden="true" />
            <span>{OPTIONAL_FIELDS_NOTE}</span>
          </p>

          <form onSubmit={submit} noValidate>
            <div className="field-grid">
              <div className="field patient-field">
                <label htmlFor="patient-identifier">
                  Identificador pseudonimizado <b aria-label="obrigatório">*</b>
                </label>
                <div className="input-wrap identifier-input">
                  <input
                    id="patient-identifier"
                    type="text"
                    autoComplete="off"
                    minLength={12}
                    maxLength={24}
                    pattern="PAC-[A-Z0-9]{8,20}"
                    required
                    value={patientIdentifier}
                    aria-invalid={Boolean(patientIdentifierError)}
                    onChange={(event) => {
                      setPatientIdentifier(event.target.value.toUpperCase());
                      setPatientIdentifierError("");
                      setPrediction(null);
                      setError("");
                    }}
                    onBlur={(event) => setPatientIdentifierError(
                      validatePatientIdentifier(event.target.value),
                    )}
                    aria-describedby={`patient-identifier-help${patientIdentifierError ? " patient-identifier-error" : ""}`}
                  />
                  <button
                    type="button"
                    onClick={copyIdentifier}
                    aria-label="Copiar identificador"
                    title="Copiar identificador"
                  >
                    {copied ? <Check size={17} /> : <Clipboard size={17} />}
                  </button>
                </div>
                <small id="patient-identifier-help">
                  Não use nome, CPF ou prontuário; mantenha a associação fora do HealthAI.
                </small>
                {copied && <small className="field-success" role="status">Identificador copiado.</small>}
                {patientIdentifierError && (
                  <small className="field-error" id="patient-identifier-error">
                    {patientIdentifierError}
                  </small>
                )}
              </div>

              {experiment.input_fields.map((field) => {
                const inputId = `assessment-${field.key}`;
                const tooltipId = `${inputId}-tooltip`;
                const rangeId = `${inputId}-range`;
                const errorId = `${inputId}-error`;
                const fieldError = fieldErrors[field.key];
                const help = FIELD_HELP[field.key] ?? "";
                const displayLabel = FIELD_LABELS[field.key] ?? field.label;
                const range = field.type === "number"
                  && field.min !== undefined
                  && field.max !== undefined
                  ? `Faixa: ${formatClinicalNumber(field.min)}–${formatClinicalNumber(field.max)}${field.unit ? ` ${field.unit}` : ""}`
                  : "";
                const describedBy = [
                  range && rangeId,
                  fieldError && errorId,
                ].filter(Boolean).join(" ") || undefined;

                return (
                  <div className="field" key={field.key}>
                    <div className="field-label-row">
                      <label htmlFor={inputId}>
                        {displayLabel}
                        {field.required && <b aria-label="obrigatório">*</b>}
                      </label>
                      {help && (
                        <FieldTooltip
                          id={tooltipId}
                          label={displayLabel}
                          text={help}
                        />
                      )}
                      {!field.required && (
                        <span className="optional-marker">Opcional</span>
                      )}
                    </div>
                    <div className="input-wrap">
                      {field.type === "select" ? (
                        <select
                          id={inputId}
                          required={field.required}
                          value={values[field.key] ?? ""}
                          aria-invalid={Boolean(fieldError)}
                          aria-describedby={describedBy}
                          onBlur={(event) => setFieldErrors((current) => ({
                            ...current,
                            [field.key]: validateField(field, event.target.value),
                          }))}
                          onChange={(event) => updateValue(field, event.target.value)}
                        >
                          <option value="">Selecione</option>
                          {field.options?.map((option) => (
                            <option value={option.value} key={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          id={inputId}
                          type="text"
                          inputMode="decimal"
                          autoComplete="off"
                          required={field.required}
                          value={values[field.key] ?? ""}
                          aria-invalid={Boolean(fieldError)}
                          aria-describedby={describedBy}
                          onBlur={(event) => setFieldErrors((current) => ({
                            ...current,
                            [field.key]: validateField(field, event.target.value),
                          }))}
                          onChange={(event) => updateValue(field, event.target.value)}
                        />
                      )}
                      {field.unit && <em>{field.unit}</em>}
                    </div>
                    {range && <small className="field-range" id={rangeId}>{range}</small>}
                    {fieldError && <small className="field-error" id={errorId}>{fieldError}</small>}
                  </div>
                );
              })}
            </div>

            {error && <ErrorSummary ref={errorRef} message={error} />}

            <div className="form-actions" aria-live="polite">
              <span>
                Campos obrigatórios preenchidos: <strong>{completedRequiredFields} de {requiredFields.length}</strong>
              </span>
              <div>
                <button
                  className="clear-form-button"
                  type="button"
                  onClick={requestClear}
                  disabled={loading}
                >
                  <RotateCcw size={16} aria-hidden="true" />
                  Limpar formulário
                </button>
                <button
                  className="primary-button"
                  type="submit"
                  disabled={loading || !allRequiredFieldsCompleted}
                >
                  {loading ? <Activity className="spin" size={17} /> : null}
                  {loading ? "Calculando..." : "Calcular avaliação"}
                  {!loading && <ArrowRight size={17} aria-hidden="true" />}
                </button>
              </div>
            </div>
          </form>
        </section>

        <ResultPanel experiment={experiment} prediction={prediction} onReset={resetForm} />
      </div>

      <ConfirmDialog
        open={confirmingClear}
        title="Limpar o formulário?"
        description="Os valores clínicos preenchidos serão removidos. Esta ação não exclui resultados já salvos."
        confirmLabel="Limpar formulário"
        onCancel={() => setConfirmingClear(false)}
        onConfirm={resetForm}
      />
    </div>
  );
}
