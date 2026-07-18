import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import type { Experiment } from "../types";
import { Assessment } from "./Assessment";

vi.mock("../api");

const experiment = {
  id: "pima",
  label: "Perfil feminino — base Pima",
  selected_model: "random_forest",
  selected_model_label: "Random Forest",
  model_version: "a1b2c3d4",
  input_fields: [
    {
      key: "glucose_mg_dl",
      label: "Glicose",
      type: "number",
      min: 44,
      max: 199,
      step: 1,
      required: true,
    },
  ],
  models: {},
} as unknown as Experiment;

describe("Assessment", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("envia medidas válidas e exibe rastreabilidade do resultado", async () => {
    vi.mocked(api.createPrediction).mockResolvedValue({
      id: 1,
      patientIdentifier: "PAC-A1B2C3D4",
      createdAt: "2026-07-11T12:00:00Z",
      experiment: "Perfil feminino — base Pima",
      model: "Random Forest",
      modelVersion: "a1b2c3d4",
      predictedClass: 0,
      probability: 0.18,
      decisionThreshold: 0.21,
      inputCompleteness: 1,
      missingFeatureCount: 0,
    });
    const onResult = vi.fn();
    const browser = userEvent.setup();
    render(<Assessment experiments={[experiment]} onResult={onResult} />);

    await browser.type(screen.getByLabelText(/Glicose/), "110");
    await browser.click(screen.getByRole("button", { name: "Calcular resultado" }));

    expect(api.createPrediction).toHaveBeenCalledWith(
      "pima",
      { glucose_mg_dl: 110 },
      expect.stringMatching(/^PAC-[A-Z0-9]{12}$/),
    );
    expect(await screen.findByText("a1b2c3d4")).toBeInTheDocument();
    expect(onResult).toHaveBeenCalledOnce();
  });

  it("aceita vírgula decimal e apresenta erro de intervalo com foco", async () => {
    const browser = userEvent.setup();
    render(<Assessment experiments={[experiment]} onResult={vi.fn()} />);

    const glucose = screen.getByLabelText(/Glicose/);
    await browser.type(glucose, "43,5");
    await browser.click(screen.getByRole("button", { name: "Calcular resultado" }));

    expect(screen.getByRole("alert")).toHaveFocus();
    expect(screen.getByText("O valor mínimo é 44.")).toBeInTheDocument();
    expect(api.createPrediction).not.toHaveBeenCalled();
  });
});
