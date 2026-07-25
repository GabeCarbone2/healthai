import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "./api";
import App from "./App";

vi.mock("./api");

const user = {
  id: 1,
  email: "medico@example.com",
  name: "Usuário Teste",
  crm: "123456",
  crm_uf: "SP",
  crm_status: "approved" as const,
  crm_verified_at: "2026-07-04T12:00:00Z",
  crm_verified_by: 2,
  crm_rejection_reason: null,
  role: "user",
  created_at: "2026-07-04T12:00:00Z",
  email_verified_at: "2026-07-04T12:00:00Z",
  privacy_accepted_at: "2026-07-04T12:00:00Z",
  privacy_notice_version: "2026-07-25.1",
  terms_accepted_at: "2026-07-04T12:00:00Z",
  terms_version: "2026-07-25.1",
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
  notice_version: "2026-07-25.1",
  result_retention_days: 180,
  contact: "privacidade@example.com",
};

const terms = {
  version: "2026-07-25.1",
  effective_date: "2026-07-25",
};

describe("App", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.fetchCurrentUser).mockResolvedValue(user);
    vi.mocked(api.fetchPrivacyInfo).mockResolvedValue(privacy);
    vi.mocked(api.fetchTermsInfo).mockResolvedValue(terms);
    vi.mocked(api.fetchCatalog).mockResolvedValue(catalog);
    vi.mocked(api.fetchResults).mockResolvedValue(emptyResults);
    vi.mocked(api.fetchCrmVerification).mockResolvedValue({
      crm_status: "pending",
      active_challenge: null,
    });
    vi.mocked(api.logout).mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("mantém a avaliação disponível quando somente o histórico falha", async () => {
    vi.mocked(api.fetchResults).mockRejectedValue(
      new Error("Falha ao carregar histórico."),
    );
    const browser = userEvent.setup();

    render(<App />);

    const resultsButton = await screen.findByRole("button", {
      name: "Histórico",
    });
    await browser.click(resultsButton);

    expect(
      await screen.findByRole("heading", { name: "Histórico indisponível" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", {
        name: "Não foi possível carregar os perfis de avaliação",
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Nova avaliação" }),
    ).toBeInTheDocument();
  });

  it("mostra o erro específico quando o catálogo falha", async () => {
    vi.mocked(api.fetchCatalog).mockRejectedValue(
      new Error("Falha ao carregar catálogo."),
    );

    render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: "Não foi possível carregar os perfis de avaliação",
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
      await screen.findByRole("button", { name: "Nova avaliação" }),
    ).toBeInTheDocument();
  });

  it("mantém cadastros pendentes fora das funções clínicas", async () => {
    vi.mocked(api.fetchCurrentUser).mockResolvedValue({
      ...user,
      crm_status: "pending",
      crm_verified_at: null,
      crm_verified_by: null,
    });

    render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: "Cadastro profissional",
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Nova avaliação" }),
    ).not.toBeInTheDocument();
    expect(api.fetchCatalog).not.toHaveBeenCalled();
  });

  it("exige aceite quando uma nova versão dos termos está vigente", async () => {
    vi.mocked(api.fetchCurrentUser).mockResolvedValue({
      ...user,
      terms_accepted_at: null,
      terms_version: null,
    });
    vi.mocked(api.acceptTermsConsent).mockResolvedValue(user);
    const browser = userEvent.setup();

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Termos de Uso" })).toBeInTheDocument();
    await browser.click(screen.getByRole("checkbox", { name: /Li e aceito/ }));
    await browser.click(screen.getByRole("button", { name: "Aceitar e continuar" }));

    expect(api.acceptTermsConsent).toHaveBeenCalledOnce();
    expect(await screen.findByRole("button", { name: "Nova avaliação" })).toBeInTheDocument();
  });

  it("pede confirmação antes de encerrar a sessão manualmente", async () => {
    const browser = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("button", { name: "Nova avaliação" }),
    ).toBeInTheDocument();

    await browser.click(screen.getByRole("button", { name: "Encerrar sessão" }));
    const dialog = screen.getByRole("dialog", { name: "Sair do HealthAI?" });

    await browser.click(within(dialog).getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(api.logout).not.toHaveBeenCalled();

    await browser.click(screen.getByRole("button", { name: "Encerrar sessão" }));
    await browser.click(
      within(screen.getByRole("dialog", { name: "Sair do HealthAI?" }))
        .getByRole("button", { name: "Sair" }),
    );

    expect(api.logout).toHaveBeenCalledOnce();
  });

  it("encerra a sessão depois de 30 minutos sem atividade", async () => {
    render(<App />);

    expect(
      await screen.findByRole("button", { name: "Nova avaliação" }),
    ).toBeInTheDocument();

    vi.useFakeTimers();
    act(() => {
      window.dispatchEvent(new Event("click"));
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30 * 60 * 1000);
    });

    expect(api.logout).toHaveBeenCalledOnce();
  });
});
