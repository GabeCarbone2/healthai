import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PatientResults } from "./PatientResults";

const result = {
  id: 7,
  patientIdentifier: "PAC-A1B2C3D4",
  createdAt: "2026-07-04T12:00:00Z",
  experiment: "Perfil feminino",
  model: "Random Forest",
  modelVersion: "abc123def456",
  predictedClass: 1,
  probability: 0.81,
  decisionThreshold: 0.35,
  inputCompleteness: 0.875,
  missingFeatureCount: 1,
};

const defaultProps = {
  results: [result],
  filters: { search: "", dateFrom: "", dateTo: "" },
  page: 1,
  pages: 2,
  total: 12,
  historyTotal: 12,
  loading: false,
  clearing: false,
  deletingId: null,
  error: "",
  notice: "",
  onRetry: vi.fn(),
  onSearch: vi.fn(),
  onPageChange: vi.fn(),
  onDelete: vi.fn(),
  onClear: vi.fn(async () => true),
  onNewAssessment: vi.fn(),
};

describe("PatientResults", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("pede confirmação antes de apagar todo o histórico", async () => {
    const browser = userEvent.setup();
    render(<PatientResults {...defaultProps} />);

    await browser.click(screen.getByRole("button", { name: "Mais ações" }));
    await browser.click(screen.getByRole("button", { name: "Limpar resultados" }));

    expect(
      screen.getByRole("alertdialog", { name: "Apagar todo o histórico?" }),
    ).toBeInTheDocument();
    expect(defaultProps.onClear).not.toHaveBeenCalled();

    await browser.click(screen.getByRole("button", { name: "Apagar tudo" }));
    expect(defaultProps.onClear).toHaveBeenCalledOnce();
  });

  it("envia os filtros de paciente e datas", async () => {
    const browser = userEvent.setup();
    render(<PatientResults {...defaultProps} />);

    await browser.type(screen.getByLabelText("Identificador"), "PAC-A1");
    await browser.type(screen.getByLabelText("Data inicial"), "01072026");
    await browser.type(screen.getByLabelText("Data final"), "04072026");
    await browser.click(screen.getByRole("button", { name: "Buscar" }));

    expect(defaultProps.onSearch).toHaveBeenCalledWith({
      search: "PAC-A1",
      dateFrom: "2026-07-01",
      dateTo: "2026-07-04",
    });
  });

  it("permite excluir um resultado e navegar entre páginas", async () => {
    const browser = userEvent.setup();
    render(<PatientResults {...defaultProps} />);

    await browser.click(
      screen.getByRole("button", {
        name: "Excluir resultado PAC-A1B2C3D4",
      }),
    );
    expect(defaultProps.onDelete).not.toHaveBeenCalled();
    await browser.click(
      screen.getByRole("button", { name: "Excluir resultado" }),
    );
    await browser.click(screen.getByRole("button", { name: "Próxima página" }));

    expect(defaultProps.onDelete).toHaveBeenCalledWith(7);
    expect(defaultProps.onPageChange).toHaveBeenCalledWith(2);
  });

  it("mostra apenas metadados persistidos nos detalhes", async () => {
    const browser = userEvent.setup();
    render(<PatientResults {...defaultProps} />);

    await browser.click(
      screen.getByRole("button", { name: "Ver detalhes de PAC-A1B2C3D4" }),
    );

    expect(screen.getByText("abc123def456")).toBeInTheDocument();
    expect(screen.getByText(/não os valores clínicos/)).toBeInTheDocument();
  });
});
