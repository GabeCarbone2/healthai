import type {
  Catalog,
  CrmVerificationChallenge,
  CrmVerificationStatus,
  PatientResult,
  PatientResultPage,
  PrivacyInfo,
  RegistrationResponse,
  ResultFilters,
  StoredPatientResult,
  StoredPatientResultPage,
  TermsInfo,
  User,
} from "./types";

async function responseError(response: Response): Promise<Error> {
  const payload = await response.json().catch(() => null);
  const validationMessage =
    payload?.detail instanceof Array
      ? payload.detail.find((item: { msg?: unknown }) =>
          typeof item?.msg === "string"
        )?.msg
      : null;
  const detail = validationMessage
    ? validationMessage.replace(/^Value error, /, "")
    : payload?.detail;
  return new Error(detail || "Não foi possível concluir a solicitação.");
}

export async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    ...options,
  });
  if (!response.ok) {
    throw await responseError(response);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function fetchCurrentUser(): Promise<User> {
  return request<User>("/auth/me");
}

export function login(email: string, password: string): Promise<User> {
  return request<User>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function register(
  name: string,
  crm: string,
  crmUf: string,
  email: string,
  password: string,
  privacyAccepted: boolean,
  termsAccepted: boolean,
): Promise<RegistrationResponse> {
  return request<RegistrationResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({
      name,
      crm,
      crm_uf: crmUf,
      email,
      password,
      privacy_accepted: privacyAccepted,
      terms_accepted: termsAccepted,
    }),
  });
}

export function verifyEmail(token: string): Promise<User> {
  return request<User>("/auth/verify-email", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export function resendVerification(email: string): Promise<void> {
  return request<void>("/auth/resend-verification", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function requestPasswordReset(email: string): Promise<void> {
  return request<void>("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function resetPassword(token: string, password: string): Promise<void> {
  return request<void>("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, password }),
  });
}

export function submitCrm(crm: string, crmUf: string): Promise<User> {
  return request<User>("/auth/crm", {
    method: "POST",
    body: JSON.stringify({ crm, crm_uf: crmUf }),
  });
}

export function fetchCrmVerification(): Promise<CrmVerificationStatus> {
  return request<CrmVerificationStatus>("/auth/crm-verification");
}

export function createCrmVerificationChallenge(): Promise<CrmVerificationChallenge> {
  return request<CrmVerificationChallenge>(
    "/auth/crm-verification/challenge",
    { method: "POST" },
  );
}

export async function downloadCrmVerificationChallenge(
  challenge: CrmVerificationChallenge,
): Promise<void> {
  const response = await fetch(`/api${challenge.download_url}`, {
    credentials: "include",
  });
  if (!response.ok) throw await responseError(response);
  const blob = await response.blob();
  const downloadUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = downloadUrl;
  anchor.download = "healthai-verificacao-crm.pdf";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(downloadUrl);
}

export function submitSignedCrmVerification(
  challengeId: number,
  signedPdf: File,
): Promise<User> {
  const form = new FormData();
  form.append("challenge_id", String(challengeId));
  form.append("signed_pdf", signedPdf);
  return request<User>("/auth/crm-verification/submit", {
    method: "POST",
    headers: {},
    body: form,
  });
}

export function logout(): Promise<void> {
  return request<void>("/auth/logout", { method: "POST" });
}

export function fetchPrivacyInfo(): Promise<PrivacyInfo> {
  return request<PrivacyInfo>("/privacy");
}

export function fetchTermsInfo(): Promise<TermsInfo> {
  return request<TermsInfo>("/terms");
}

export function acceptPrivacyConsent(): Promise<User> {
  return request<User>("/auth/privacy-consent", {
    method: "POST",
    body: JSON.stringify({ accepted: true }),
  });
}

export function acceptTermsConsent(): Promise<User> {
  return request<User>("/auth/terms-consent", {
    method: "POST",
    body: JSON.stringify({ accepted: true }),
  });
}

export function deleteAccount(password: string): Promise<void> {
  return request<void>("/auth/account", {
    method: "DELETE",
    body: JSON.stringify({ password, confirmation: "EXCLUIR" }),
  });
}

export function fetchCatalog(): Promise<Catalog> {
  return request<Catalog>("/models");
}

export function createPrediction(
  experiment: string,
  values: Record<string, string | number | null>,
  patientIdentifier: string,
): Promise<PatientResult> {
  return request<StoredPatientResult>(`/predict/${experiment}`, {
    method: "POST",
    body: JSON.stringify({
      ...values,
      patient_identifier: patientIdentifier,
    }),
  }).then(mapStoredResult);
}

function mapStoredResult(result: StoredPatientResult): PatientResult {
  return {
    id: result.id,
    patientIdentifier: result.patient_identifier,
    createdAt: result.created_at,
    experiment: result.experiment,
    model: result.model,
    modelVersion: result.model_version,
    predictedClass: result.predicted_class,
    probability: result.probability,
    decisionThreshold: result.decision_threshold,
    inputCompleteness: result.input_completeness,
    missingFeatureCount: result.missing_feature_count,
    localExplanation: result.local_explanation,
  };
}

export async function fetchResults(
  page = 1,
  filters?: ResultFilters,
): Promise<PatientResultPage> {
  const query = new URLSearchParams({
    page: String(page),
    page_size: "10",
  });
  if (filters?.search.trim()) query.set("search", filters.search.trim());
  if (filters?.dateFrom) query.set("date_from", filters.dateFrom);
  if (filters?.dateTo) query.set("date_to", filters.dateTo);

  const results = await request<StoredPatientResultPage>(
    `/results?${query.toString()}`,
  );
  return {
    items: results.items.map(mapStoredResult),
    total: results.total,
    page: results.page,
    pageSize: results.page_size,
    pages: results.pages,
  };
}

export function clearResults(): Promise<void> {
  return request<void>("/results", { method: "DELETE" });
}

export function deleteResult(resultId: number): Promise<void> {
  return request<void>(`/results/${resultId}`, { method: "DELETE" });
}
