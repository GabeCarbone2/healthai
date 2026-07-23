import {
  Activity,
  ClipboardPlus,
  ListChecks,
  LogOut,
  RefreshCw,
  ShieldEllipsis,
  ShieldCheck,
  WifiOff,
} from "lucide-react";
import { useEffect, useState } from "react";

import {
  clearResults,
  deleteResult as deleteStoredResult,
  fetchCatalog,
  fetchCurrentUser,
  fetchPrivacyInfo,
  fetchResults,
  fetchTermsInfo,
  logout,
} from "./api";
import { HealthAiLogo } from "./components/HealthAiLogo";
import { PageFooter } from "./components/PageFooter";
import { ConfirmDialog } from "./components/ConfirmDialog";
import { Assessment } from "./pages/Assessment";
import { AccountPage } from "./pages/AccountPage";
import { AdminCrmPage } from "./pages/AdminCrmPage";
import { AuthPage } from "./pages/AuthPage";
import { PatientResults } from "./pages/PatientResults";
import { PrivacyConsentPage } from "./pages/PrivacyConsentPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { TermsConsentPage } from "./pages/TermsConsentPage";
import { TermsPage } from "./pages/TermsPage";
import { VerifyEmailPage } from "./pages/VerifyEmailPage";
import { useScrollMotion } from "./hooks/useScrollMotion";
import type {
  Catalog,
  PatientResult,
  PatientResultPage,
  PrivacyInfo,
  ResultFilters,
  TermsInfo,
  User,
} from "./types";

type Page = "assessment" | "results" | "account" | "admin";

const clinicalNavigation = [
  { id: "assessment" as const, label: "Nova avaliação", icon: ClipboardPlus },
  { id: "results" as const, label: "Histórico", icon: ListChecks },
];
const accountNavigation = {
  id: "account" as const,
  label: "Conta",
  icon: ShieldCheck,
};
const adminNavigation = {
  id: "admin" as const,
  label: "Análises de acesso",
  icon: ShieldEllipsis,
};
const INACTIVITY_TIMEOUT_MS = 30 * 60 * 1000;
const ACTIVITY_EVENTS = [
  "click",
  "keydown",
  "pointerdown",
  "scroll",
  "touchstart",
] as const;

const EMPTY_FILTERS: ResultFilters = {
  search: "",
  dateFrom: "",
  dateTo: "",
};

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export default function App() {
  useScrollMotion();
  const [page, setPage] = useState<Page>("assessment");
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [patientResults, setPatientResults] = useState<PatientResult[]>([]);
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const [privacyInfo, setPrivacyInfo] = useState<
    PrivacyInfo | null | undefined
  >(undefined);
  const [termsInfo, setTermsInfo] = useState<TermsInfo | null | undefined>(undefined);
  const [catalogError, setCatalogError] = useState("");
  const [resultsError, setResultsError] = useState("");
  const [resultsNotice, setResultsNotice] = useState("");
  const [resultsLoading, setResultsLoading] = useState(false);
  const [clearingResults, setClearingResults] = useState(false);
  const [deletingResultId, setDeletingResultId] = useState<number | null>(null);
  const [resultFilters, setResultFilters] =
    useState<ResultFilters>(EMPTY_FILTERS);
  const [resultPage, setResultPage] = useState(1);
  const [resultPages, setResultPages] = useState(1);
  const [resultTotal, setResultTotal] = useState(0);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [loggingOut, setLoggingOut] = useState(false);
  const [confirmingLogout, setConfirmingLogout] = useState(false);
  const [logoutError, setLogoutError] = useState("");
  const verificationRoute = window.location.pathname === "/verify-email";
  const forgotPasswordRoute = window.location.pathname === "/forgot-password";
  const resetPasswordRoute = window.location.pathname === "/reset-password";
  const termsRoute = window.location.pathname === "/terms";
  const verificationToken = verificationRoute
    ? new URLSearchParams(window.location.search).get("token") ?? ""
    : "";
  const resetToken = resetPasswordRoute
    ? new URLSearchParams(window.location.search).get("token") ?? ""
    : "";

  useEffect(() => {
    fetchCurrentUser()
      .then(setUser)
      .catch(() => setUser(null));
    fetchPrivacyInfo()
      .then(setPrivacyInfo)
      .catch(() => setPrivacyInfo(null));
    fetchTermsInfo()
      .then(setTermsInfo)
      .catch(() => setTermsInfo(null));
  }, []);

  useEffect(() => {
    if (
      !user
      || !privacyInfo
      || !termsInfo
      || user.crm_status !== "approved"
      || !user.privacy_accepted_at
      || user.privacy_notice_version !== privacyInfo.notice_version
      || !user.terms_accepted_at
      || user.terms_version !== termsInfo.version
    ) {
      return;
    }
    let active = true;
    setCatalogError("");
    setResultsError("");
    setResultsNotice("");
    setResultsLoading(true);

    fetchCatalog()
      .then((nextCatalog) => {
        if (active) setCatalog(nextCatalog);
      })
      .catch((requestError) => {
        if (active) {
          setCatalogError(
            errorMessage(
              requestError,
              "Não foi possível carregar os perfis de avaliação.",
            ),
          );
        }
      });

    fetchResults(1, EMPTY_FILTERS)
      .then((results) => {
        if (!active) return;
        setPatientResults(results.items);
        setResultPage(results.page);
        setResultPages(results.pages);
        setResultTotal(results.total);
        setHistoryTotal(results.total);
      })
      .catch((requestError) => {
        if (active) {
          setResultsError(
            errorMessage(
              requestError,
              "Não foi possível carregar o histórico.",
            ),
          );
        }
      })
      .finally(() => {
        if (active) setResultsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [privacyInfo, termsInfo, user]);

  useEffect(() => {
    if (!user) return;

    let timeoutId = window.setTimeout(() => {
      void expireIdleSession();
    }, INACTIVITY_TIMEOUT_MS);

    function resetTimer() {
      window.clearTimeout(timeoutId);
      timeoutId = window.setTimeout(() => {
        void expireIdleSession();
      }, INACTIVITY_TIMEOUT_MS);
    }

    ACTIVITY_EVENTS.forEach((eventName) => {
      window.addEventListener(eventName, resetTimer, { passive: true });
    });

    return () => {
      window.clearTimeout(timeoutId);
      ACTIVITY_EVENTS.forEach((eventName) => {
        window.removeEventListener(eventName, resetTimer);
      });
    };
  }, [user]);

  async function retryPrivacyInfo() {
    setPrivacyInfo(undefined);
    setTermsInfo(undefined);
    try {
      const [privacy, terms] = await Promise.all([
        fetchPrivacyInfo(),
        fetchTermsInfo(),
      ]);
      setPrivacyInfo(privacy);
      setTermsInfo(terms);
    } catch {
      setPrivacyInfo(null);
      setTermsInfo(null);
    }
  }

  async function retryCatalog() {
    setCatalog(null);
    setCatalogError("");
    try {
      setCatalog(await fetchCatalog());
    } catch (requestError) {
      setCatalogError(
        errorMessage(
          requestError,
          "Não foi possível carregar os perfis de avaliação.",
        ),
      );
    }
  }

  function storeResults(results: PatientResultPage, filters: ResultFilters) {
    setPatientResults(results.items);
    setResultPage(results.page);
    setResultPages(results.pages);
    setResultTotal(results.total);
    if (!filters.search && !filters.dateFrom && !filters.dateTo) {
      setHistoryTotal(results.total);
    }
  }

  async function loadResults(
    pageNumber = resultPage,
    filters = resultFilters,
  ) {
    setResultsLoading(true);
    setResultsError("");
    setResultsNotice("");
    try {
      storeResults(await fetchResults(pageNumber, filters), filters);
      return true;
    } catch (requestError) {
      setResultsError(
        errorMessage(requestError, "Não foi possível carregar o histórico."),
      );
      return false;
    } finally {
      setResultsLoading(false);
    }
  }

  async function searchResults(filters: ResultFilters) {
    setResultFilters(filters);
    await loadResults(1, filters);
  }

  async function removeResults(): Promise<boolean> {
    setClearingResults(true);
    setResultsError("");
    setResultsNotice("");
    try {
      await clearResults();
      setPatientResults([]);
      setResultPage(1);
      setResultPages(1);
      setResultTotal(0);
      setHistoryTotal(0);
      setResultFilters(EMPTY_FILTERS);
      setResultsNotice("Resultados apagados com sucesso.");
      return true;
    } catch (requestError) {
      setResultsError(
        errorMessage(requestError, "Não foi possível apagar os resultados."),
      );
      return false;
    } finally {
      setClearingResults(false);
    }
  }

  async function removeResult(resultId: number) {
    setDeletingResultId(resultId);
    setResultsError("");
    setResultsNotice("");
    try {
      await deleteStoredResult(resultId);
      setHistoryTotal((current) => Math.max(0, current - 1));
      const targetPage =
        patientResults.length === 1 && resultPage > 1
          ? resultPage - 1
          : resultPage;
      if (await loadResults(targetPage, resultFilters)) {
        setResultsNotice("Resultado excluído com sucesso.");
      }
    } catch (requestError) {
      setResultsError(
        errorMessage(requestError, "Não foi possível excluir o resultado."),
      );
    } finally {
      setDeletingResultId(null);
    }
  }

  async function endSession() {
    setLoggingOut(true);
    setConfirmingLogout(false);
    setLogoutError("");
    try {
      await logout();
      clearLocalAccount();
      return true;
    } catch (requestError) {
      setLogoutError(
        errorMessage(requestError, "Não foi possível encerrar a sessão."),
      );
      return false;
    } finally {
      setLoggingOut(false);
    }
  }

  async function expireIdleSession() {
    setLogoutError("");
    await logout().catch(() => undefined);
    clearLocalAccount();
  }

  function clearLocalAccount() {
    setUser(null);
    setCatalog(null);
    setPatientResults([]);
    setResultFilters(EMPTY_FILTERS);
    setResultPage(1);
    setResultPages(1);
    setResultTotal(0);
    setHistoryTotal(0);
    setPage("assessment");
  }

  if (verificationRoute) {
    return (
      <VerifyEmailPage
        token={verificationToken}
        onVerified={(verifiedUser) => {
          window.history.replaceState({}, "", "/");
          setUser(verifiedUser);
        }}
      />
    );
  }

  if (forgotPasswordRoute || resetPasswordRoute || termsRoute) {
    if (privacyInfo === undefined || termsInfo === undefined) {
      return <div className="loading-state"><Activity size={24} /><span>Carregando...</span></div>;
    }
    if (!privacyInfo || !termsInfo) {
      return (
        <div className="connection-error">
          <WifiOff size={28} />
          <h1>Conteúdo indisponível</h1>
          <p>Não foi possível carregar as configurações públicas.</p>
          <button type="button" className="retry-button" onClick={retryPrivacyInfo}>
            <RefreshCw size={16} /> Tentar novamente
          </button>
        </div>
      );
    }
    if (termsRoute) return <TermsPage info={termsInfo} privacy={privacyInfo} />;
    if (forgotPasswordRoute) return <ForgotPasswordPage privacy={privacyInfo} />;
    return <ResetPasswordPage token={resetToken} privacy={privacyInfo} />;
  }

  if (user === undefined || privacyInfo === undefined || termsInfo === undefined) {
    return (
      <div className="loading-state">
        <Activity size={24} />
        <span>Carregando sessão...</span>
      </div>
    );
  }

  if (!privacyInfo || !termsInfo) {
    return (
      <div className="connection-error">
        <WifiOff size={28} />
        <h1>Aviso de privacidade indisponível</h1>
        <p>Não foi possível carregar as configurações de privacidade.</p>
        <button
          type="button"
          className="retry-button"
          onClick={retryPrivacyInfo}
        >
          <RefreshCw size={16} />
          Tentar novamente
        </button>
      </div>
    );
  }

  if (!user) {
    return <AuthPage onAuthenticated={setUser} privacy={privacyInfo} />;
  }

  if (
    !user.privacy_accepted_at
    || user.privacy_notice_version !== privacyInfo.notice_version
  ) {
    return (
      <PrivacyConsentPage
        info={privacyInfo}
        onAccepted={setUser}
        onLogout={endSession}
        onAccountDeleted={clearLocalAccount}
      />
    );
  }

  if (!user.terms_accepted_at || user.terms_version !== termsInfo.version) {
    return (
      <TermsConsentPage
        info={termsInfo}
        privacy={privacyInfo}
        onAccepted={setUser}
        onLogout={endSession}
      />
    );
  }

  const clinicalAccess = user.crm_status === "approved";
  const adminAccess = user.role === "admin";
  const navigation = [
    ...(clinicalAccess ? clinicalNavigation : []),
    accountNavigation,
    ...(adminAccess ? [adminNavigation] : []),
  ];
  const effectivePage: Page =
    page === "admin" && !adminAccess
      ? "account"
      : (page === "assessment" || page === "results") && !clinicalAccess
        ? "account"
        : page;

  return (
    <div className="app-shell">
      <div className="app-monogram" aria-hidden="true">
        <HealthAiLogo className="app-monogram-logo" />
      </div>

      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <span className="brand-mark">
              <HealthAiLogo className="healthai-logo" title="HealthAI" />
            </span>
            <span className="brand-copy">
              <strong>HealthAI</strong>
              <small>Apoio à triagem</small>
            </span>
          </div>

          <nav className="primary-nav" aria-label="Navegação principal">
            {navigation.map((item) => (
              <button
                type="button"
                className={effectivePage === item.id ? "active" : ""}
                aria-current={effectivePage === item.id ? "page" : undefined}
                onClick={() => setPage(item.id)}
                key={item.id}
              >
                <item.icon size={18} />
                {item.label}
              </button>
            ))}
          </nav>

          <div className="account-summary">
            <span>{user.name.slice(0, 1).toUpperCase()}</span>
            <div>
              <strong>{user.name}</strong>
              {user.crm_status === "approved" && <em>Cadastro aprovado</em>}
            </div>
            <button
              type="button"
              onClick={() => setConfirmingLogout(true)}
              disabled={loggingOut}
              title={loggingOut ? "Encerrando sessão..." : "Encerrar sessão"}
              aria-label="Encerrar sessão"
            >
              {loggingOut ? <Activity size={17} /> : <LogOut size={17} />}
            </button>
          </div>
        </div>
      </header>

      <main>
        {logoutError && (
          <div className="app-message error" role="alert">
            {logoutError} Tente novamente.
          </div>
        )}
        <ConfirmDialog
          open={confirmingLogout}
          title="Sair do HealthAI?"
          description="Você será desconectado desta sessão. Para voltar, basta entrar novamente com seu e-mail e senha."
          confirmLabel="Sair"
          busyLabel="Saindo..."
          busy={loggingOut}
          icon={<LogOut size={28} aria-hidden="true" />}
          tone="neutral"
          onCancel={() => setConfirmingLogout(false)}
          onConfirm={async () => {
            await endSession();
          }}
        />
        {effectivePage === "admin" ? (
          <AdminCrmPage />
        ) : effectivePage === "account" ? (
          <AccountPage
            user={user}
            privacy={privacyInfo}
            onDeleted={clearLocalAccount}
            onUserUpdated={setUser}
          />
        ) : catalogError ? (
          <div className="connection-error">
            <WifiOff size={28} />
            <h1>Não foi possível carregar os perfis de avaliação</h1>
            <p>{catalogError}</p>
            <button type="button" className="retry-button" onClick={retryCatalog}>
              <RefreshCw size={16} />
              Tentar novamente
            </button>
          </div>
        ) : !catalog ? (
          <div className="loading-state">
            <Activity size={24} />
            <span>Carregando perfis de avaliação...</span>
          </div>
        ) : effectivePage === "assessment" ? (
          <Assessment
            experiments={catalog.experiments}
            onResult={() => {
              setResultFilters(EMPTY_FILTERS);
              setResultsError("");
              setResultsNotice("");
              void loadResults(1, EMPTY_FILTERS);
            }}
          />
        ) : effectivePage === "results" ? (
          <PatientResults
            results={patientResults}
            filters={resultFilters}
            page={resultPage}
            pages={resultPages}
            total={resultTotal}
            historyTotal={historyTotal}
            loading={resultsLoading}
            clearing={clearingResults}
            deletingId={deletingResultId}
            error={resultsError}
            notice={resultsNotice}
            onRetry={() => {
              void loadResults();
            }}
            onSearch={searchResults}
            onPageChange={(nextPage) => {
              void loadResults(nextPage);
            }}
            onDelete={removeResult}
            onClear={removeResults}
            onNewAssessment={() => setPage("assessment")}
          />
        ) : null}
      </main>
      <PageFooter contact={privacyInfo.contact} />
    </div>
  );
}
