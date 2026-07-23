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
    expect(screen.getByText(/1 campo foi estimado/)).toBeInTheDocument();
    expect(screen.getByText(/não representa diagnóstico médico/)).toBeInTheDocument();
    const technicalSummary = screen.getByText("Detalhes técnicos da avaliação");
    expect(technicalSummary).toHaveAttribute("aria-expanded", "false");
    await browser.click(technicalSummary);
    expect(technicalSummary).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByRole("heading", { name: "Fatores mais considerados pelo sistema" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/não explicam individualmente este resultado/)).toBeInTheDocument();
    const localSummary = screen.getByText("Informações consideradas nesta avaliação");
    expect(localSummary).toHaveAttribute("aria-expanded", "false");
    await browser.click(localSummary);
    expect(screen.getByText("Variações estimadas nesta avaliação")).toBeInTheDocument();
    expect(screen.getByText(/elevou 8.0 p.p./)).toBeInTheDocument();
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
