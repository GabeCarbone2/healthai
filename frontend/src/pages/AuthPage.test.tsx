import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { AccountPage } from "./AccountPage";
import { AuthPage } from "./AuthPage";

vi.mock("../api");

const privacy = {
  notice_version: "2026-07-25.1",
  result_retention_days: 180,
  contact: "privacidade@example.com",
};

const registeredUser = {
  id: 1,
  email: "usuario@example.com",
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

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.fetchCrmVerification).mockResolvedValue({
    crm_status: "pending",
    active_challenge: null,
  });
});

describe("AuthPage", () => {
  it("apresenta a estrutura pública sem esconder o acesso profissional", () => {
    render(
      <AuthPage
        onAuthenticated={vi.fn()}
        privacy={privacy}
      />,
    );

    expect(
      screen.getByRole("heading", {
        name: "Apoio à triagem de risco de diabetes",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("navigation", { name: "Navegação pública" }),
    ).toBeInTheDocument();
    const publicNavigation = screen.getByRole("navigation", {
      name: "Navegação pública",
    });
    expect(within(publicNavigation).getByRole("link", { name: "Como funciona" }))
      .toHaveAttribute("href", "#como-funciona");
    expect(within(publicNavigation).getByRole("link", { name: "Segurança e privacidade" }))
      .toHaveAttribute("href", "#seguranca");
    expect(within(publicNavigation).getByRole("link", { name: "Limitações" }))
      .toHaveAttribute("href", "#limitacoes");
    expect(screen.getByRole("link", { name: "Entrar" }))
      .toHaveAttribute("href", "#acesso");
    expect(
      screen.getByRole("link", { name: "Entrar na plataforma" }),
    ).toHaveAttribute("href", "#acesso");
    expect(screen.getAllByRole("link", { name: "Como funciona" }).at(-1))
      .toHaveAttribute("href", "#como-funciona");
    expect(
      screen.getByRole("heading", {
        name: "Da informação disponível à leitura contextualizada.",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Perfil para mulher adulta" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Perfil para adulto" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Acesso profissional controlado" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/análise administrativa do cadastro profissional/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/ROLAGEM/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/verificação automática/i)).not.toBeInTheDocument();
    expect(
      screen.getAllByText(/não substitui diagnóstico, exames, avaliação médica ou julgamento clínico/i),
    ).toHaveLength(3);
    expect(screen.getByLabelText("E-mail")).toBeInTheDocument();
    expect(screen.getByLabelText("Senha")).toBeInTheDocument();
  });

  it("expõe e fecha o menu público com estado acessível", async () => {
    const browser = userEvent.setup();
    render(
      <AuthPage
        onAuthenticated={vi.fn()}
        privacy={privacy}
      />,
    );

    const menuButton = screen.getByRole("button", { name: "Abrir menu" });
    expect(menuButton).toHaveAttribute("aria-expanded", "false");

    await browser.click(menuButton);
    expect(
      screen.getByRole("button", { name: "Fechar menu" }),
    ).toHaveAttribute("aria-expanded", "true");

    await browser.keyboard("{Escape}");
    expect(
      screen.getByRole("button", { name: "Abrir menu" }),
    ).toHaveAttribute("aria-expanded", "false");
  });

  it("envia o consentimento explícito ao criar a conta", async () => {
    vi.mocked(api.register).mockResolvedValue({
      email: registeredUser.email,
      verification_required: true,
      expires_in_seconds: 86400,
      email_sent: true,
    });
    const onAuthenticated = vi.fn();
    const browser = userEvent.setup();
    render(
      <AuthPage
        onAuthenticated={onAuthenticated}
        privacy={privacy}
      />,
    );

    await browser.click(screen.getByRole("button", { name: "Criar conta" }));
    await browser.type(screen.getByLabelText("Nome"), "Usuário Teste");
    await browser.type(screen.getByLabelText("CRM"), "123456");
    await browser.selectOptions(screen.getByLabelText("UF do CRM"), "SP");
    await browser.type(
      screen.getByLabelText("E-mail"),
      "usuario@example.com",
    );
    await browser.type(screen.getByLabelText("Senha"), "senha-segura");
    await browser.type(
      screen.getByLabelText("Confirmar senha"),
      "senha-segura",
    );
    await browser.click(
      screen.getByRole("checkbox", {
        name: /Li o aviso e consinto/,
      }),
    );
    await browser.click(
      screen.getByRole("checkbox", { name: /Li e aceito os Termos/ }),
    );
    await browser.click(
      screen.getByRole("button", { name: "Criar minha conta" }),
    );

    expect(api.register).toHaveBeenCalledWith(
      "Usuário Teste",
      "123456",
      "SP",
      "usuario@example.com",
      "senha-segura",
      true,
      true,
    );
    expect(onAuthenticated).not.toHaveBeenCalled();
    expect(
      screen.getByRole("heading", { name: "Verifique seu e-mail" }),
    ).toBeInTheDocument();
  });
});

describe("AccountPage", () => {
  it("exige senha e confirmação antes de excluir a conta", async () => {
    vi.mocked(api.deleteAccount).mockResolvedValue();
    const onDeleted = vi.fn();
    const browser = userEvent.setup();
    render(
      <AccountPage
        user={registeredUser}
        privacy={privacy}
        onDeleted={onDeleted}
        onUserUpdated={vi.fn()}
      />,
    );

    await browser.click(
      screen.getByRole("button", { name: "Excluir minha conta" }),
    );
    await browser.type(
      screen.getByLabelText("Confirme sua senha"),
      "senha-segura",
    );
    await browser.type(
      screen.getByLabelText("Digite EXCLUIR para confirmar"),
      "EXCLUIR",
    );
    await browser.click(
      screen.getByRole("button", { name: "Excluir permanentemente" }),
    );

    expect(api.deleteAccount).toHaveBeenCalledWith("senha-segura");
    expect(onDeleted).toHaveBeenCalledOnce();
  });

  it("envia o PDF assinado do desafio e atualiza o usuário", async () => {
    const pendingUser = {
      ...registeredUser,
      crm_status: "pending" as const,
      crm_verified_at: null,
      crm_verified_by: null,
    };
    const challenge = {
      id: 42,
      created_at: "2026-07-25T12:00:00Z",
      expires_at: "2026-07-25T12:30:00Z",
      download_url: "/auth/crm-verification/challenge/42/document",
    };
    vi.mocked(api.fetchCrmVerification).mockResolvedValue({
      crm_status: "pending",
      active_challenge: challenge,
    });
    vi.mocked(api.submitSignedCrmVerification).mockResolvedValue(
      registeredUser,
    );
    const onUserUpdated = vi.fn();
    const browser = userEvent.setup();
    render(
      <AccountPage
        user={pendingUser}
        privacy={privacy}
        onDeleted={vi.fn()}
        onUserUpdated={onUserUpdated}
      />,
    );

    expect(
      await screen.findByRole("button", { name: "Baixar novamente" }),
    ).toBeInTheDocument();
    const signedPdf = new File(["signed"], "crm-assinado.pdf", {
      type: "application/pdf",
    });
    await browser.upload(
      screen.getByLabelText(/^PDF assinado/),
      signedPdf,
    );
    const submitButton = screen.getByRole("button", {
      name: "Enviar PDF assinado",
    });
    await waitFor(() => expect(submitButton).toBeEnabled());
    await browser.click(submitButton);

    await waitFor(() => expect(
      api.submitSignedCrmVerification,
    ).toHaveBeenCalledWith(
      challenge.id,
      expect.objectContaining({ name: "crm-assinado.pdf" }),
    ));
    expect(onUserUpdated).toHaveBeenCalledWith(
      registeredUser,
    );
  });
});
