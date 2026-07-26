import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { Experiment } from "../types";
import { ResultPanel } from "./ResultPanel";

const experiment = {
  id: "pima",
  label: "Perfil feminino — base Pima",
  selected_model: "random_forest",
  selected_model_label: "Random Forest",
  model_version: "a1b2c3d4",
  input_fields: [{ key: "glucose_mg_dl", label: "Glicose", type: "number" }],
  models: {
    random_forest: {
      explainability: {
        features: [
          { feature: "glucose_mg_dl", importance_mean: 0.2, importance_std: 0 },
        ],
      },
    },
  },
} as unknown as Experiment;

describe("ResultPanel", () => {
  it("separa explicação global e informa limites e imputação", async () => {
    const browser = userEvent.setup();
    render(
      <ResultPanel
        experiment={experiment}
        patientIdentifier="PAC-A1B2C3D4"
        performedAt="2026-07-25T20:10:00-03:00"
        estimatedFieldLabels={["Glicose"]}
        prediction={{
          experiment: "pima",
          model: "random_forest",
          model_version: "a1b2c3d4",
          predicted_class: 1,
          probability: 0.42,
          decision_threshold: 0.21,
          input_completeness: 0.875,
          missing_feature_count: 1,
          local_explanation: {
            method: "single_feature_reference_replacement",
            interpretation: "Efeitos locais não causais e não aditivos.",
            features: [
              {
                feature: "glucose_mg_dl",
                probability_effect: 0.08,
                direction: "increases",
              },
            ],
          },
        }}
      />,
    );

    expect(
      screen.getByRole("progressbar", {
        name: "Probabilidade estimada de risco",
      }),
    ).toHaveAttribute("value", "42");
    expect(screen.getByText("Referência de atenção utilizada")).toBeInTheDocument();
    expect(screen.getByText(/1 campo foi substituído/)).toBeInTheDocument();
    expect(screen.getByText("Glicose", { selector: "li" })).toBeInTheDocument();
    expect(screen.getByText(/não representa diagnóstico médico/)).toBeInTheDocument();
    expect(screen.getByText("PAC-A1B2C3D4")).toBeInTheDocument();
    const technicalSummary = screen.getByText("Transparência técnica da avaliação");
    expect(technicalSummary).toHaveAttribute("aria-expanded", "false");
    await browser.click(technicalSummary);
    expect(technicalSummary).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByRole("heading", { name: "Informações com maior influência geral no sistema" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Não explicam individualmente esta avaliação/)).toBeInTheDocument();
    const localSummary = screen.getByText("Análise técnica de sensibilidade");
    expect(localSummary).toHaveAttribute("aria-expanded", "false");
    await browser.click(localSummary);
    expect(screen.getByText(/Os efeitos não são causais nem aditivos/)).toBeInTheDocument();
    expect(screen.getByText(/\+8,0 pontos percentuais/)).toBeInTheDocument();
    expect(screen.queryByText(/elevou|reduziu/i)).not.toBeInTheDocument();
  });

  it("mantém o estado vazio curto e sem lista antecipada", () => {
    render(<ResultPanel experiment={experiment} prediction={null} />);

    expect(screen.getByText("Pronto para calcular")).toBeInTheDocument();
    expect(
      screen.getByText("Preencha os campos obrigatórios para gerar a avaliação."),
    ).toBeInTheDocument();
    expect(screen.queryByText("probabilidade estimada;")).not.toBeInTheDocument();
  });
});
