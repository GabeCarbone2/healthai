import type {
  Catalog,
  PatientResult,
  PatientResultPage,
  PrivacyInfo,
  RegistrationResponse,
  ResultFilters,
  StoredPatientResult,
  StoredPatientResultPage,
  User,
} from "./types";

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
    const payload = await response.json().catch(() => null);
    const detail =
      payload?.detail instanceof Array
        ? "Revise os valores informados."
        : payload?.detail;
    throw new Error(detail || "Não foi possível concluir a solicitação.");
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

export function logout(): Promise<void> {
  return request<void>("/auth/logout", { method: "POST" });
}

export function fetchPrivacyInfo(): Promise<PrivacyInfo> {
  return request<PrivacyInfo>("/privacy");
}

export function acceptPrivacyConsent(): Promise<User> {
  return request<User>("/auth/privacy-consent", {
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
    predictedClass: result.predicted_class,
    probability: result.probability,
    decisionThreshold: result.decision_threshold,
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
