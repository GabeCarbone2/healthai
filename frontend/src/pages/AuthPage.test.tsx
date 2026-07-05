import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { AccountPage } from "./AccountPage";
import { AuthPage } from "./AuthPage";

vi.mock("../api");

const privacy = {
  notice_version: "2026-07-05.1",
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
  privacy_notice_version: "2026-07-05.1",
};

describe("AuthPage", () => {
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
      screen.getByRole("button", { name: "Criar minha conta" }),
    );

    expect(api.register).toHaveBeenCalledWith(
      "Usuário Teste",
      "123456",
      "SP",
      "usuario@example.com",
      "senha-segura",
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
});
