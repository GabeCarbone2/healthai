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
  logout,
} from "./api";
import { Assessment } from "./pages/Assessment";
import { AccountPage } from "./pages/AccountPage";
import { AdminCrmPage } from "./pages/AdminCrmPage";
import { AuthPage } from "./pages/AuthPage";
import { PatientResults } from "./pages/PatientResults";
import { PrivacyConsentPage } from "./pages/PrivacyConsentPage";
import { VerifyEmailPage } from "./pages/VerifyEmailPage";
import type {
  Catalog,
  PatientResult,
  PatientResultPage,
  PrivacyInfo,
  ResultFilters,
  User,
} from "./types";

type Page = "assessment" | "results" | "account" | "admin";

const clinicalNavigation = [
  { id: "assessment" as const, label: "Avaliação", icon: ClipboardPlus },
  { id: "results" as const, label: "Resultados", icon: ListChecks },
];
const accountNavigation = {
  id: "account" as const,
  label: "Conta",
  icon: ShieldCheck,
};
const adminNavigation = {
  id: "admin" as const,
  label: "Verificações",
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
  const [page, setPage] = useState<Page>("assessment");
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [patientResults, setPatientResults] = useState<PatientResult[]>([]);
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const [privacyInfo, setPrivacyInfo] = useState<
    PrivacyInfo | null | undefined
  >(undefined);
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
  const [logoutError, setLogoutError] = useState("");
  const verificationRoute = window.location.pathname === "/verify-email";
  const verificationToken = verificationRoute
    ? new URLSearchParams(window.location.search).get("token") ?? ""
    : "";

  useEffect(() => {
    fetchCurrentUser()
      .then(setUser)
      .catch(() => setUser(null));
    fetchPrivacyInfo()
      .then(setPrivacyInfo)
      .catch(() => setPrivacyInfo(null));
  }, []);

  useEffect(() => {
    if (
      !user
      || !privacyInfo
      || user.crm_status !== "approved"
      || !user.privacy_accepted_at
      || user.privacy_notice_version !== privacyInfo.notice_version
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
              "Não foi possível carregar o catálogo de modelos.",
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
  }, [privacyInfo, user]);

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
    try {
      setPrivacyInfo(await fetchPrivacyInfo());
    } catch {
      setPrivacyInfo(null);
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
          "Não foi possível carregar o catálogo de modelos.",
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

  if (user === undefined || privacyInfo === undefined) {
    return (
      <div className="loading-state">
        <Activity size={24} />
        <span>Carregando sessão...</span>
      </div>
    );
  }

  if (!privacyInfo) {
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

  const clinicalAccess = user.crm_status === "approved";
  const adminAccess = user.role === "admin";
  const navigation = [
    ...(clinicalAccess ? clinicalNavigation : []),
    accountNavigation,
    ...(adminAccess ? [adminNavigation] : []),
  ];
  const effectivePage: Page =
    page === "admin" && adminAccess
      ? "admin"
      : (page === "assessment" || page === "results") && !clinicalAccess
        ? "account"
        : page;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <span className="brand-mark">
              <Activity size={21} />
            </span>
            <strong>HealthAI</strong>
          </div>

          <nav className="primary-nav">
            {navigation.map((item) => (
              <button
                type="button"
                className={effectivePage === item.id ? "active" : ""}
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
              <small>{user.email}</small>
            </div>
            <button
              type="button"
              onClick={endSession}
              disabled={loggingOut}
              title={loggingOut ? "Saindo..." : "Sair"}
              aria-label={loggingOut ? "Saindo..." : "Sair"}
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
            <h1>Não foi possível carregar os modelos</h1>
            <p>{catalogError}</p>
            <button type="button" className="retry-button" onClick={retryCatalog}>
              <RefreshCw size={16} />
              Tentar novamente
            </button>
          </div>
        ) : !catalog ? (
          <div className="loading-state">
            <Activity size={24} />
            <span>Carregando modelos...</span>
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
          />
        ) : null}
      </main>
    </div>
  );
}
