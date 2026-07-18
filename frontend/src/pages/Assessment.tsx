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
    description: "Perfil acadêmico baseado no conjunto Pima.",
  },
  nhanes: {
    title: "NHANES — adultos",
    short: "Adultos",
    description: "Perfil acadêmico baseado no conjunto NHANES.",
  },
} as const;

const FIELD_HELP: Record<string, string> = {
  diabetes_pedigree_function:
    "Índice histórico da base Pima; consulte a documentação do estudo.",
  skin_thickness_mm:
    "Se não estiver disponível, deixe em branco para o pipeline estimar.",
  insulin_miu_l:
    "Se não estiver disponível, deixe em branco para o pipeline estimar.",
};

function createPatientIdentifier() {
  const randomPart = crypto.randomUUID().replaceAll("-", "").slice(0, 12);
  return `PAC-${randomPart.toUpperCase()}`;
}

function parseDecimal(value: string) {
  return Number(value.trim().replace(",", "."));
}

function validateField(field: InputField, value: string) {
  if (!value.trim()) return field.required ? "Preencha este campo." : "";
  if (field.type === "select") return "";

  const number = parseDecimal(value);
  if (!Number.isFinite(number)) return "Informe um número válido.";
  if (field.min !== undefined && number < field.min) {
    return `O valor mínimo é ${field.min}.`;
  }
  if (field.max !== undefined && number > field.max) {
    return `O valor máximo é ${field.max}.`;
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
  const [values, setValues] = useState<Record<string, string>>({});
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const errorRef = useRef<HTMLDivElement>(null);
  const experiment = useMemo(
    () =>
      experiments.find((item) => item.id === experimentId) ?? experiments[0],
    [experimentId, experiments],
  );

  useEffect(() => {
    setValues({});
    setFieldErrors({});
    setPatientIdentifier(createPatientIdentifier());
    setPrediction(null);
    setError("");
    setCopied(false);
  }, [experimentId]);

  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  if (!experiment) return null;

  const presentation = PRESENTATION[experiment.id];

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
    const nextErrors = Object.fromEntries(
      experiment.input_fields.map((field) => [
        field.key,
        validateField(field, values[field.key] ?? ""),
      ]),
    );
    setFieldErrors(nextErrors);
    if (Object.values(nextErrors).some(Boolean)) {
      setError("Há campos ausentes ou com valores fora do intervalo permitido.");
      return;
    }

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
      setLoading(false);
    }
  }

  function clear() {
    setValues({});
    setFieldErrors({});
    setPatientIdentifier(createPatientIdentifier());
    setPrediction(null);
    setError("");
    setCopied(false);
  }

  return (
    <div className="page assessment-page">
      <header className="page-header assessment-header">
        <div>
          <span className="page-eyebrow">Apoio acadêmico à decisão</span>
          <h1>Nova avaliação</h1>
          <p>Preencha as medidas disponíveis e revise antes de calcular.</p>
        </div>
        <div className="model-switch" aria-label="Tipo de avaliação">
          {experiments.map((item) => (
            <button
              key={item.id}
              className={item.id === experiment.id ? "active" : ""}
              aria-pressed={item.id === experiment.id}
              type="button"
              onClick={() => setExperimentId(item.id)}
            >
              <strong>{PRESENTATION[item.id].title}</strong>
              <small>{PRESENTATION[item.id].description}</small>
            </button>
          ))}
        </div>
      </header>

      <details className="model-context">
        <summary>
          <Info size={16} aria-hidden="true" />
          Sobre este perfil e suas limitações
        </summary>
        <div>
          <p>
            <strong>{presentation.title}</strong> usa {experiment.n_train} registros
            de treino e {experiment.n_test} de teste da base {experiment.source_dataset}.
          </p>
          <p>
            Modelo selecionado: {experiment.selected_model_label}. Resultados não
            equivalem a diagnóstico, risco futuro validado ou recomendação clínica.
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
            <button
              className="clear-form-button"
              type="button"
              onClick={clear}
            >
              <RotateCcw size={16} aria-hidden="true" />
              Limpar formulário
            </button>
          </div>

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
                    onChange={(event) => {
                      setPatientIdentifier(event.target.value.toUpperCase());
                      setPrediction(null);
                      setError("");
                    }}
                    aria-describedby="patient-identifier-help"
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
                  Não informe nome, CPF ou prontuário. Guarde a associação fora do HealthAI.
                </small>
                {copied && <small className="field-success" role="status">Identificador copiado.</small>}
              </div>

              {experiment.input_fields.map((field) => {
                const inputId = `assessment-${field.key}`;
                const helpId = `${inputId}-help`;
                const errorId = `${inputId}-error`;
                const fieldError = fieldErrors[field.key];
                const help = FIELD_HELP[field.key]
                  ?? (!field.required
                    ? "Opcional. Em branco, o pipeline usa uma estimativa estatística."
                    : "");

                return (
                  <div className="field" key={field.key}>
                    <label htmlFor={inputId}>
                      {field.label}
                      {field.required && <b aria-label="obrigatório">*</b>}
                    </label>
                    <div className="input-wrap">
                      {field.type === "select" ? (
                        <select
                          id={inputId}
                          required={field.required}
                          value={values[field.key] ?? ""}
                          aria-invalid={Boolean(fieldError)}
                          aria-describedby={[help && helpId, fieldError && errorId].filter(Boolean).join(" ") || undefined}
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
                          placeholder="0"
                          required={field.required}
                          value={values[field.key] ?? ""}
                          aria-invalid={Boolean(fieldError)}
                          aria-describedby={[help && helpId, fieldError && errorId].filter(Boolean).join(" ") || undefined}
                          onBlur={(event) => setFieldErrors((current) => ({
                            ...current,
                            [field.key]: validateField(field, event.target.value),
                          }))}
                          onChange={(event) => updateValue(field, event.target.value)}
                        />
                      )}
                      {field.unit && <em>{field.unit}</em>}
                    </div>
                    {help && <small id={helpId}>{help}</small>}
                    {fieldError && <small className="field-error" id={errorId}>{fieldError}</small>}
                  </div>
                );
              })}
            </div>

            {error && <ErrorSummary ref={errorRef} message={error} />}

            <div className="form-actions">
              <span>* Campos obrigatórios</span>
              <button className="primary-button" type="submit" disabled={loading}>
                {loading ? <Activity className="spin" size={17} /> : null}
                {loading ? "Calculando..." : "Calcular resultado"}
                {!loading && <ArrowRight size={17} aria-hidden="true" />}
              </button>
            </div>
          </form>
        </section>

        <ResultPanel experiment={experiment} prediction={prediction} onReset={clear} />
      </div>
    </div>
  );
}
