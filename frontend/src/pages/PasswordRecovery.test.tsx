import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { ForgotPasswordPage } from "./ForgotPasswordPage";
import { ResetPasswordPage } from "./ResetPasswordPage";

vi.mock("../api");

const privacy = {
  notice_version: "2026-07-11.1",
  result_retention_days: 180,
  contact: "privacidade@example.com",
};

describe("recuperação de senha", () => {
  beforeEach(() => vi.clearAllMocks());

  it("solicita o link sem revelar se a conta existe", async () => {
    vi.mocked(api.requestPasswordReset).mockResolvedValue();
    const browser = userEvent.setup();
    render(<ForgotPasswordPage privacy={privacy} />);

    await browser.type(screen.getByLabelText("E-mail"), "medico@example.com");
    await browser.click(screen.getByRole("button", { name: "Enviar link de recuperação" }));

    expect(api.requestPasswordReset).toHaveBeenCalledWith("medico@example.com");
    expect(await screen.findByRole("heading", { name: "Confira seu e-mail" })).toBeInTheDocument();
    expect(screen.getByText(/resposta é sempre a mesma/)).toBeInTheDocument();
  });

  it("valida a confirmação e redefine com token", async () => {
    vi.mocked(api.resetPassword).mockResolvedValue();
    const browser = userEvent.setup();
    render(<ResetPasswordPage token="token-seguro-com-mais-de-32-caracteres" privacy={privacy} />);

    await browser.type(screen.getByLabelText("Nova senha"), "nova-senha-segura");
    await browser.type(screen.getByLabelText("Confirmar nova senha"), "nova-senha-segura");
    await browser.click(screen.getByRole("button", { name: "Redefinir senha" }));

    expect(api.resetPassword).toHaveBeenCalledWith(
      "token-seguro-com-mais-de-32-caracteres",
      "nova-senha-segura",
    );
    expect(await screen.findByRole("heading", { name: "Redefinição concluída" })).toBeInTheDocument();
  });
});
