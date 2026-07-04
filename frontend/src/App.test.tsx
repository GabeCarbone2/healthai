import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "./api";
import App from "./App";

vi.mock("./api");

const user = {
  id: 1,
  email: "medico@example.com",
  name: "Usuário Teste",
  role: "user",
  created_at: "2026-07-04T12:00:00Z",
  email_verified_at: "2026-07-04T12:00:00Z",
  privacy_accepted_at: "2026-07-04T12:00:00Z",
  privacy_notice_version: "2026-07-04.2",
};

const catalog = {
  experiments: [],
  model_labels: {},
};

const emptyResults = {
  items: [],
  total: 0,
  page: 1,
  pageSize: 10,
  pages: 1,
};

const privacy = {
  notice_version: "2026-07-04.2",
  result_retention_days: 180,
  contact: "privacidade@example.com",
};

describe("App", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.fetchCurrentUser).mockResolvedValue(user);
    vi.mocked(api.fetchPrivacyInfo).mockResolvedValue(privacy);
    vi.mocked(api.fetchCatalog).mockResolvedValue(catalog);
    vi.mocked(api.fetchResults).mockResolvedValue(emptyResults);
  });

  it("mantém a avaliação disponível quando somente o histórico falha", async () => {
    vi.mocked(api.fetchResults).mockRejectedValue(
      new Error("Falha ao carregar histórico."),
    );
    const browser = userEvent.setup();

    render(<App />);

    const resultsButton = await screen.findByRole("button", {
      name: "Resultados",
    });
    await browser.click(resultsButton);

    expect(
      await screen.findByRole("heading", { name: "Histórico indisponível" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", {
        name: "Não foi possível carregar os modelos",
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Avaliação" }),
    ).toBeInTheDocument();
  });

  it("mostra o erro específico quando o catálogo falha", async () => {
    vi.mocked(api.fetchCatalog).mockRejectedValue(
      new Error("Falha ao carregar catálogo."),
    );

    render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: "Não foi possível carregar os modelos",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Falha ao carregar catálogo.")).toBeInTheDocument();
  });

  it("exige novo aceite quando o aviso de privacidade não foi aceito", async () => {
    const pendingUser = {
      ...user,
      privacy_accepted_at: null,
      privacy_notice_version: null,
    };
    vi.mocked(api.fetchCurrentUser).mockResolvedValue(pendingUser);
    vi.mocked(api.acceptPrivacyConsent).mockResolvedValue(user);
    const browser = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Aviso de privacidade" }),
    ).toBeInTheDocument();
    await browser.click(
      screen.getByRole("checkbox", {
        name: /Li o aviso e consinto/,
      }),
    );
    await browser.click(
      screen.getByRole("button", { name: "Aceitar e continuar" }),
    );

    expect(api.acceptPrivacyConsent).toHaveBeenCalledOnce();
    expect(
      await screen.findByRole("button", { name: "Avaliação" }),
    ).toBeInTheDocument();
  });
});
