import {
  Activity,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  ListChecks,
  RefreshCw,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import type { PatientResult, ResultFilters } from "../types";

type Props = {
  results: PatientResult[];
  filters: ResultFilters;
  page: number;
  pages: number;
  total: number;
  historyTotal: number;
  loading: boolean;
  clearing: boolean;
  deletingId: number | null;
  error: string;
  notice: string;
  onRetry: () => void | Promise<void>;
  onSearch: (filters: ResultFilters) => void | Promise<void>;
  onPageChange: (page: number) => void | Promise<void>;
  onDelete: (resultId: number) => void | Promise<void>;
  onClear: () => Promise<boolean>;
};

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

export function PatientResults({
  results,
  filters,
  page,
  pages,
  total,
  historyTotal,
  loading,
  clearing,
  deletingId,
  error,
  notice,
  onRetry,
  onSearch,
  onPageChange,
  onDelete,
  onClear,
}: Props) {
  const [draftFilters, setDraftFilters] = useState(filters);
  const [confirmingClear, setConfirmingClear] = useState(false);
  const hasFilters = Boolean(
    filters.search || filters.dateFrom || filters.dateTo,
  );

  useEffect(() => {
    setDraftFilters(filters);
  }, [filters]);

  useEffect(() => {
    if (!confirmingClear) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape" && !clearing) setConfirmingClear(false);
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [clearing, confirmingClear]);

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    void onSearch(draftFilters);
  }

  function clearFilters() {
    const emptyFilters = { search: "", dateFrom: "", dateTo: "" };
    setDraftFilters(emptyFilters);
    void onSearch(emptyFilters);
  }

  async function confirmClear() {
    if (await onClear()) setConfirmingClear(false);
  }

  return (
    <div className="page results-page">
      <header className="page-header">
        <div>
          <h1>Resultados</h1>
          <p>Histórico de avaliações realizadas.</p>
        </div>
        {historyTotal > 0 && (
          <button
            type="button"
            className="clear-results"
            onClick={() => setConfirmingClear(true)}
            disabled={clearing || deletingId !== null}
          >
            {clearing ? <Activity size={16} /> : <Trash2 size={16} />}
            {clearing ? "Limpando..." : "Limpar resultados"}
          </button>
        )}
      </header>

      <form className="results-filters" onSubmit={submitSearch}>
        <label className="results-search">
          <span>Identificador</span>
          <div>
            <Search size={16} />
            <input
              type="search"
              placeholder="Ex.: PAC-A1B2C3D4"
              maxLength={24}
              value={draftFilters.search}
              onChange={(event) =>
                setDraftFilters((current) => ({
                  ...current,
                  search: event.target.value,
                }))
              }
            />
          </div>
        </label>
        <label>
          <span>Data inicial</span>
          <input
            type="date"
            max={draftFilters.dateTo || undefined}
            value={draftFilters.dateFrom}
            onChange={(event) =>
              setDraftFilters((current) => ({
                ...current,
                dateFrom: event.target.value,
              }))
            }
          />
        </label>
        <label>
          <span>Data final</span>
          <input
            type="date"
            min={draftFilters.dateFrom || undefined}
            value={draftFilters.dateTo}
            onChange={(event) =>
              setDraftFilters((current) => ({
                ...current,
                dateTo: event.target.value,
              }))
            }
          />
        </label>
        <div className="filter-actions">
          {hasFilters && (
            <button
              type="button"
              className="filter-clear"
              onClick={clearFilters}
              disabled={loading || deletingId !== null}
            >
              <X size={15} />
              Limpar
            </button>
          )}
          <button
            type="submit"
            className="filter-submit"
            disabled={loading || deletingId !== null}
          >
            <Search size={15} />
            Buscar
          </button>
        </div>
      </form>

      <section className="patient-results">
        {notice && (
          <div className="results-message success" role="status">
            <CheckCircle2 size={17} />
            {notice}
          </div>
        )}
        {error && results.length > 0 && (
          <div className="results-message error" role="alert">
            <AlertCircle size={17} />
            <span>{error}</span>
            <button type="button" onClick={onRetry} disabled={loading}>
              <RefreshCw size={15} />
              Tentar novamente
            </button>
          </div>
        )}

        {loading && results.length === 0 ? (
          <div className="empty-results loading-results">
            <Activity size={30} />
            <h2>Carregando histórico...</h2>
          </div>
        ) : error && results.length === 0 ? (
          <div className="empty-results history-error">
            <AlertCircle size={30} />
            <h2>Histórico indisponível</h2>
            <p>{error}</p>
            <button type="button" className="retry-button" onClick={onRetry}>
              <RefreshCw size={16} />
              Tentar novamente
            </button>
          </div>
        ) : results.length === 0 ? (
          <div className="empty-results">
            <ListChecks size={30} />
            <h2>
              {hasFilters
                ? "Nenhum resultado encontrado"
                : "Nenhuma avaliação realizada"}
            </h2>
            <p>
              {hasFilters
                ? "Revise os filtros ou limpe a busca."
                : "Os resultados aparecerão aqui após o primeiro cálculo."}
            </p>
          </div>
        ) : (
          <>
            <div className="table-scroll">
              <table className="metrics-table patient-table">
                <thead>
                  <tr>
                    <th>Identificador</th>
                    <th>Data</th>
                    <th>Base</th>
                    <th>Modelo</th>
                    <th>Resultado</th>
                    <th>Probabilidade</th>
                    <th>Limiar</th>
                    <th aria-label="Ações" />
                  </tr>
                </thead>
                <tbody>
                  {results.map((result) => (
                    <tr key={result.id}>
                      <td>
                        <strong>{result.patientIdentifier}</strong>
                      </td>
                      <td>{formatDate(result.createdAt)}</td>
                      <td>{result.experiment}</td>
                      <td>{result.model}</td>
                      <td>
                        <span
                          className={`result-class ${
                            result.predictedClass === 1 ? "positive" : "negative"
                          }`}
                        >
                          {result.predictedClass === 1
                            ? "Acima do limiar"
                            : "Abaixo do limiar"}
                        </span>
                      </td>
                      <td>{percent(result.probability)}</td>
                      <td>{percent(result.decisionThreshold)}</td>
                      <td>
                        <button
                          type="button"
                          className="delete-result"
                          onClick={() => onDelete(result.id)}
                          disabled={deletingId !== null}
                          title={`Excluir resultado ${result.patientIdentifier}`}
                          aria-label={`Excluir resultado ${result.patientIdentifier}`}
                        >
                          {deletingId === result.id ? (
                            <Activity size={15} />
                          ) : (
                            <Trash2 size={15} />
                          )}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <footer className="results-pagination">
              <span>
                {total} {total === 1 ? "resultado" : "resultados"}
              </span>
              <div>
                <button
                  type="button"
                  onClick={() => onPageChange(page - 1)}
                  disabled={loading || deletingId !== null || page <= 1}
                  aria-label="Página anterior"
                >
                  <ChevronLeft size={16} />
                </button>
                <strong>
                  Página {page} de {pages}
                </strong>
                <button
                  type="button"
                  onClick={() => onPageChange(page + 1)}
                  disabled={loading || deletingId !== null || page >= pages}
                  aria-label="Próxima página"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            </footer>
          </>
        )}
      </section>

      {confirmingClear && (
        <div
          className="confirm-overlay"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !clearing) {
              setConfirmingClear(false);
            }
          }}
        >
          <div
            className="confirm-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="clear-results-title"
            aria-describedby="clear-results-description"
          >
            <AlertCircle size={28} />
            <h2 id="clear-results-title">Apagar todo o histórico?</h2>
            <p id="clear-results-description">
              Esta ação excluirá permanentemente {historyTotal}{" "}
              {historyTotal === 1 ? "resultado" : "resultados"} da sua conta e
              não poderá ser desfeita.
            </p>
            <div>
              <button
                type="button"
                className="dialog-cancel"
                onClick={() => setConfirmingClear(false)}
                disabled={clearing}
                autoFocus
              >
                Cancelar
              </button>
              <button
                type="button"
                className="dialog-confirm"
                onClick={confirmClear}
                disabled={clearing}
              >
                {clearing ? <Activity size={16} /> : <Trash2 size={16} />}
                {clearing ? "Apagando..." : "Apagar tudo"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
