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

const nhanesExperiment = {
  ...experiment,
  id: "nhanes",
  label: "Perfil adulto — base NHANES",
  selected_model: "logistic_regression",
  selected_model_label: "Regressão logística",
  input_fields: [
    {
      key: "bmi_kg_m2",
      label: "IMC",
      type: "number",
      min: 12,
      max: 70,
      required: true,
    },
  ],
} as unknown as Experiment;

describe("Assessment", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("inicia medidas vazias e bloqueia o cálculo enquanto falta obrigatório", async () => {
    const browser = userEvent.setup();
    render(<Assessment experiments={[experiment]} onResult={vi.fn()} />);

    const glucose = screen.getByLabelText(/Glicose/);
    expect(glucose).toHaveValue("");
    expect(glucose).not.toHaveAttribute("placeholder", "0");
    expect(screen.getByText(/Campos obrigatórios preenchidos:/)).toHaveTextContent("0 de 1");
    expect(
      screen.getByRole("button", { name: "Calcular avaliação" }),
    ).toBeDisabled();
    const limitations = screen.getByText("Detalhes técnicos e limitações do perfil");
    expect(limitations).toHaveAttribute("aria-expanded", "false");
    await browser.click(limitations);
    expect(limitations).toHaveAttribute("aria-expanded", "true");
  });

  it("mantém a seleção entre os perfis Pima e NHANES", async () => {
    const browser = userEvent.setup();
    render(
      <Assessment
        experiments={[experiment, nhanesExperiment]}
        onResult={vi.fn()}
      />,
    );

    const pimaButton = screen.getByRole("button", {
      name: /Mulher adulta/,
    });
    const nhanesButton = screen.getByRole("button", {
      name: /Adulto/,
    });
    expect(pimaButton).toHaveAttribute("aria-pressed", "true");
    expect(nhanesButton).toHaveAttribute("aria-pressed", "false");

    await browser.click(nhanesButton);

    expect(nhanesButton).toHaveAttribute("aria-pressed", "true");
    expect(pimaButton).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByText(/Perfil selecionado:/)).toHaveTextContent(
      "Perfil selecionado: Adulto",
    );
    expect(screen.getByLabelText(/IMC/)).toHaveValue("");
  });

  it("diferencia zero informado de campo opcional vazio no payload", async () => {
    const zeroExperiment = {
      ...experiment,
      input_fields: [
        {
          key: "pregnancies",
          label: "Gestações",
          type: "number",
          min: 0,
          max: 17,
          step: 1,
          required: true,
        },
        {
          key: "diastolic_bp_mmhg",
          label: "Pressão diastólica",
          type: "number",
          min: 30,
          max: 122,
        },
      ],
    } as Experiment;
    vi.mocked(api.createPrediction).mockResolvedValue({
      id: 2,
      patientIdentifier: "PAC-A1B2C3D4",
      createdAt: "2026-07-11T12:00:00Z",
      experiment: "Perfil feminino — base Pima",
      model: "Random Forest",
      modelVersion: "a1b2c3d4",
      predictedClass: 0,
      probability: 0.18,
      decisionThreshold: 0.21,
      inputCompleteness: 0.5,
      missingFeatureCount: 1,
    });
    const browser = userEvent.setup();
    render(<Assessment experiments={[zeroExperiment]} onResult={vi.fn()} />);

    expect(
      screen.getAllByText(/Campo opcional. Se não informado/),
    ).toHaveLength(1);
    expect(screen.getByText("Opcional")).toBeInTheDocument();
    const tooltipTrigger = screen.getByRole("button", {
      name: "Ajuda sobre Gestações",
    });
    expect(tooltipTrigger).toHaveAttribute(
      "aria-describedby",
      "assessment-pregnancies-tooltip",
    );
    tooltipTrigger.focus();
    expect(tooltipTrigger).toHaveFocus();
    expect(screen.getByRole("tooltip")).toHaveTextContent(
      "Número de gestações informadas.",
    );

    await browser.type(
      screen.getByRole("textbox", { name: /Gestações/ }),
      "0",
    );
    await browser.click(screen.getByRole("button", { name: "Calcular avaliação" }));

    expect(api.createPrediction).toHaveBeenCalledWith(
      "pima",
      { pregnancies: 0, diastolic_bp_mmhg: null },
      expect.stringMatching(/^PAC-[A-Z0-9]{12}$/),
    );
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
    await browser.click(screen.getByRole("button", { name: "Calcular avaliação" }));

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
    await browser.click(screen.getByRole("button", { name: "Calcular avaliação" }));

    expect(screen.getByRole("alert")).toHaveFocus();
    expect(screen.getByText("O valor mínimo permitido é 44.")).toBeInTheDocument();
    expect(api.createPrediction).not.toHaveBeenCalled();
  });
});
