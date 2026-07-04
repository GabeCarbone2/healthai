import { ArrowRight, RotateCcw } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { createPrediction } from "../api";
import { ResultPanel } from "../components/ResultPanel";
import type { Experiment, PatientResult, Prediction } from "../types";

type Props = {
  experiments: Experiment[];
  onResult: (result: PatientResult) => void;
};

function createPatientIdentifier() {
  const randomPart = crypto.randomUUID().replaceAll("-", "").slice(0, 12);
  return `PAC-${randomPart.toUpperCase()}`;
}

export function Assessment({ experiments, onResult }: Props) {
  const [experimentId, setExperimentId] = useState(experiments[0]?.id);
  const [patientIdentifier, setPatientIdentifier] = useState(
    createPatientIdentifier,
  );
  const [values, setValues] = useState<Record<string, string>>({});
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const experiment = useMemo(
    () =>
      experiments.find((item) => item.id === experimentId) ?? experiments[0],
    [experimentId, experiments],
  );

  useEffect(() => {
    setValues({});
    setPatientIdentifier(createPatientIdentifier());
    setPrediction(null);
    setError("");
  }, [experimentId]);

  if (!experiment) return null;

  function updateValue(key: string, value: string) {
    setValues((current) => ({ ...current, [key]: value }));
    setPrediction(null);
    setError("");
  }

  function validationMessage(
    input: HTMLInputElement | HTMLSelectElement,
    minimum?: number,
    maximum?: number,
  ) {
    if (input.validity.valueMissing) return "Preencha este campo.";
    if (input.validity.rangeUnderflow) {
      return `Informe um valor maior ou igual a ${minimum}.`;
    }
    if (input.validity.rangeOverflow) {
      return `Informe um valor menor ou igual a ${maximum}.`;
    }
    if (input.validity.stepMismatch) {
      return "Informe um valor válido para este campo.";
    }
    return "";
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    const payload = Object.fromEntries(
      experiment.input_fields.map((field) => {
        const value = values[field.key];
        if (!value) return [field.key, null];
        return [field.key, field.type === "number" ? Number(value) : value];
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
        predicted_class: savedResult.predictedClass,
        probability: savedResult.probability,
        decision_threshold: savedResult.decisionThreshold,
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
    setPatientIdentifier(createPatientIdentifier());
    setPrediction(null);
    setError("");
  }

  return (
    <div className="page assessment-page">
      <header className="page-header">
        <div>
          <h1>Nova avaliação</h1>
        </div>
        <div className="model-switch" aria-label="Base do experimento">
          {experiments.map((item) => (
            <button
              key={item.id}
              className={item.id === experiment.id ? "active" : ""}
              type="button"
              onClick={() => setExperimentId(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </header>

      <div className="assessment-layout">
        <section className="form-section">
          <div className="section-heading">
            <div>
              <h2>Informações do paciente</h2>
              <p>
                {experiment.label} · {experiment.selected_model_label}
              </p>
            </div>
            <button
              className="icon-button"
              type="button"
              onClick={clear}
              title="Limpar formulário"
              aria-label="Limpar formulário"
            >
              <RotateCcw size={18} />
            </button>
          </div>

          <form onSubmit={submit}>
            <div className="field-grid">
              <label className="field patient-field">
                <span>
                  Identificador pseudonimizado
                  <b aria-label="obrigatório">*</b>
                </span>
                <div className="input-wrap">
                  <input
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
                  />
                </div>
                <small>
                  Use apenas este código. Não informe nome, CPF ou prontuário.
                </small>
              </label>
              {experiment.input_fields.map((field) => (
                <label className="field" key={field.key}>
                  <span>
                    {field.label}
                    {field.required && <b aria-label="obrigatório">*</b>}
                  </span>
                  <div className="input-wrap">
                    {field.type === "select" ? (
                      <select
                        required={field.required}
                        value={values[field.key] ?? ""}
                        onInvalid={(event) =>
                          event.currentTarget.setCustomValidity(
                            validationMessage(event.currentTarget),
                          )
                        }
                        onInput={(event) =>
                          event.currentTarget.setCustomValidity("")
                        }
                        onChange={(event) =>
                          updateValue(field.key, event.target.value)
                        }
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
                        type="number"
                        inputMode="decimal"
                        min={field.min}
                        max={field.max}
                        step={field.step}
                        required={field.required}
                        value={values[field.key] ?? ""}
                        onInvalid={(event) =>
                          event.currentTarget.setCustomValidity(
                            validationMessage(
                              event.currentTarget,
                              field.min,
                              field.max,
                            ),
                          )
                        }
                        onInput={(event) =>
                          event.currentTarget.setCustomValidity("")
                        }
                        onChange={(event) =>
                          updateValue(field.key, event.target.value)
                        }
                      />
                    )}
                    {field.unit && <em>{field.unit}</em>}
                  </div>
                </label>
              ))}
            </div>

            {error && <div className="form-error">{error}</div>}

            <div className="form-actions">
              <span>* Campos obrigatórios</span>
              <button className="primary-button" type="submit" disabled={loading}>
                {loading ? "Calculando..." : "Calcular"}
                {!loading && <ArrowRight size={17} />}
              </button>
            </div>
          </form>
        </section>

        <ResultPanel experiment={experiment} prediction={prediction} />
      </div>
    </div>
  );
}
