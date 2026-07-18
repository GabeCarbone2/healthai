import {
  Activity,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  Download,
  Eye,
  ListChecks,
  MoreHorizontal,
  RefreshCw,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { Fragment, FormEvent, useEffect, useMemo, useState } from "react";

import { ConfirmDialog } from "../components/ConfirmDialog";
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

type SortKey = "createdAt" | "patientIdentifier" | "probability";

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function displayVersion(value: string) {
  return value && !/legacy|unknown|unversioned/i.test(value)
    ? value
    : "Não registrada";
}

function csvCell(value: string | number) {
  const safe = String(value).replaceAll('"', '""');
  return `"${safe}"`;
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
  const [confirmingDelete, setConfirmingDelete] = useState<PatientResult | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("createdAt");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
  const [actionsOpen, setActionsOpen] = useState(false);
  const hasFilters = Boolean(filters.search || filters.dateFrom || filters.dateTo);

  const sortedResults = useMemo(() => {
    return [...results].sort((first, second) => {
      const a = first[sortKey];
      const b = second[sortKey];
      const comparison = typeof a === "number"
        ? a - (b as number)
        : String(a).localeCompare(String(b), "pt-BR");
      return sortDirection === "asc" ? comparison : -comparison;
    });
  }, [results, sortDirection, sortKey]);

  useEffect(() => {
    setDraftFilters(filters);
  }, [filters]);

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    void onSearch(draftFilters);
  }

  function clearFilters() {
    const emptyFilters = { search: "", dateFrom: "", dateTo: "" };
    setDraftFilters(emptyFilters);
    void onSearch(emptyFilters);
  }

  function sortBy(nextKey: SortKey) {
    if (sortKey === nextKey) {
      setSortDirection((current) => current === "asc" ? "desc" : "asc");
    } else {
      setSortKey(nextKey);
      setSortDirection(nextKey === "createdAt" ? "desc" : "asc");
    }
  }

  function exportCurrentPage() {
    const headers = [
      "Identificador", "Data", "Perfil", "Modelo", "Versão", "Resultado",
      "Probabilidade", "Limiar", "Completude", "Medidas estimadas",
    ];
    const rows = sortedResults.map((result) => [
      result.patientIdentifier,
      result.createdAt,
      result.experiment,
      result.model,
      displayVersion(result.modelVersion),
      result.predictedClass === 1 ? "Acima do limiar" : "Abaixo do limiar",
      result.probability,
      result.decisionThreshold,
      result.inputCompleteness,
      result.missingFeatureCount,
    ]);
    const csv = [headers, ...rows]
      .map((row) => row.map(csvCell).join(";"))
      .join("\n");
    const url = URL.createObjectURL(
      new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `healthai-resultados-pagina-${page}.csv`;
    link.click();
    URL.revokeObjectURL(url);
    setActionsOpen(false);
  }

  async function confirmClear() {
    if (await onClear()) setConfirmingClear(false);
  }

  async function confirmDelete() {
    if (!confirmingDelete) return;
    await onDelete(confirmingDelete.id);
    setConfirmingDelete(null);
  }

  return (
    <div className="page results-page">
      <header className="page-header">
        <div>
          <span className="page-eyebrow">Rastreabilidade</span>
          <h1>Resultados</h1>
          <p>Histórico de avaliações e metadados armazenados.</p>
        </div>
        {historyTotal > 0 && (
          <div className="results-actions">
            <button
              type="button"
              className="secondary-button"
              aria-expanded={actionsOpen}
              aria-controls="results-actions-menu"
              onClick={() => setActionsOpen((current) => !current)}
            >
              <MoreHorizontal size={17} aria-hidden="true" />
              Mais ações
              <ChevronDown size={15} aria-hidden="true" />
            </button>
            {actionsOpen && (
              <div className="results-actions-menu" id="results-actions-menu">
                <button type="button" onClick={exportCurrentPage}>
                  <Download size={16} aria-hidden="true" />
                  Exportar página em CSV
                </button>
                <button
                  type="button"
                  className="danger-action"
                  onClick={() => {
                    setActionsOpen(false);
                    setConfirmingClear(true);
                  }}
                  disabled={clearing || deletingId !== null}
                >
                  <Trash2 size={16} aria-hidden="true" />
                  Limpar resultados
                </button>
              </div>
            )}
          </div>
        )}
      </header>

      <form className="results-filters" onSubmit={submitSearch} lang="pt-BR">
        <label className="results-search">
          <span>Identificador</span>
          <div>
            <Search size={16} aria-hidden="true" />
            <input
              type="search"
              placeholder="Ex.: PAC-A1B2C3D4"
              maxLength={24}
              value={draftFilters.search}
              onChange={(event) => setDraftFilters((current) => ({
                ...current,
                search: event.target.value.toUpperCase(),
              }))}
            />
          </div>
        </label>
        <label>
          <span>Data inicial</span>
          <input
            type="date"
            max={draftFilters.dateTo || undefined}
            value={draftFilters.dateFrom}
            onChange={(event) => setDraftFilters((current) => ({
              ...current,
              dateFrom: event.target.value,
            }))}
          />
        </label>
        <label>
          <span>Data final</span>
          <input
            type="date"
            min={draftFilters.dateFrom || undefined}
            value={draftFilters.dateTo}
            onChange={(event) => setDraftFilters((current) => ({
              ...current,
              dateTo: event.target.value,
            }))}
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
              <X size={15} aria-hidden="true" />
              Limpar filtros
            </button>
          )}
          <button
            type="submit"
            className="filter-submit"
            disabled={loading || deletingId !== null}
          >
            <Search size={15} aria-hidden="true" />
            Buscar
          </button>
        </div>
      </form>

      <section className="patient-results" aria-labelledby="history-table-title">
        <h2 className="sr-only" id="history-table-title">Histórico de resultados</h2>
        {notice && (
          <div className="results-message success" role="status">
            <CheckCircle2 size={17} aria-hidden="true" />
            {notice}
          </div>
        )}
        {error && results.length > 0 && (
          <div className="results-message error" role="alert">
            <AlertCircle size={17} aria-hidden="true" />
            <span>{error}</span>
            <button type="button" onClick={onRetry} disabled={loading}>
              <RefreshCw size={15} aria-hidden="true" />
              Tentar novamente
            </button>
          </div>
        )}

        {loading && results.length === 0 ? (
          <div className="empty-results loading-results">
            <Activity size={30} className="spin" />
            <h2>Carregando histórico...</h2>
          </div>
        ) : error && results.length === 0 ? (
          <div className="empty-results history-error">
            <AlertCircle size={30} />
            <h2>Histórico indisponível</h2>
            <p>{error}</p>
            <button type="button" className="retry-button" onClick={onRetry}>
              <RefreshCw size={16} aria-hidden="true" />
              Tentar novamente
            </button>
          </div>
        ) : results.length === 0 ? (
          <div className="empty-results">
            <ListChecks size={30} />
            <h2>{hasFilters ? "Nenhum resultado encontrado" : "Nenhuma avaliação realizada"}</h2>
            <p>{hasFilters ? "Revise os filtros ou limpe a busca." : "Os resultados aparecerão aqui após o primeiro cálculo."}</p>
          </div>
        ) : (
          <>
            <div className="table-scroll">
              <table className="metrics-table patient-table">
                <caption>
                  Exibindo {results.length} de {total} resultado(s). A ordenação atua nesta página.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">
                      <button type="button" className="sort-button" onClick={() => sortBy("patientIdentifier")}>
                        Identificador <ChevronsUpDown size={14} />
                      </button>
                    </th>
                    <th scope="col">
                      <button type="button" className="sort-button" onClick={() => sortBy("createdAt")}>
                        Data <ChevronsUpDown size={14} />
                      </button>
                    </th>
                    <th scope="col" className="secondary-column">Perfil</th>
                    <th scope="col" className="secondary-column">Modelo</th>
                    <th scope="col">Resultado</th>
                    <th scope="col">
                      <button type="button" className="sort-button" onClick={() => sortBy("probability")}>
                        Probabilidade <ChevronsUpDown size={14} />
                      </button>
                    </th>
                    <th scope="col" className="secondary-column">Limiar</th>
                    <th scope="col"><span className="sr-only">Ações</span></th>
                  </tr>
                </thead>
                <tbody>
                  {sortedResults.map((result) => (
                    <Fragment key={result.id}>
                      <tr>
                        <td><strong>{result.patientIdentifier}</strong></td>
                        <td>{formatDate(result.createdAt)}</td>
                        <td className="secondary-column">{result.experiment}</td>
                        <td className="secondary-column">{result.model}</td>
                        <td>
                          <span className={`result-class ${result.predictedClass === 1 ? "positive" : "negative"}`}>
                            {result.predictedClass === 1 ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
                            {result.predictedClass === 1 ? "Acima do limiar" : "Abaixo do limiar"}
                          </span>
                        </td>
                        <td>{percent(result.probability)}</td>
                        <td className="secondary-column">{percent(result.decisionThreshold)}</td>
                        <td>
                          <div className="row-actions">
                            <button
                              type="button"
                              onClick={() => setExpandedId((current) => current === result.id ? null : result.id)}
                              aria-expanded={expandedId === result.id}
                              aria-label={`Ver detalhes de ${result.patientIdentifier}`}
                              title="Ver detalhes"
                            >
                              <Eye size={15} />
                            </button>
                            <button
                              type="button"
                              className="delete-result"
                              onClick={() => setConfirmingDelete(result)}
                              disabled={deletingId !== null}
                              aria-label={`Excluir resultado ${result.patientIdentifier}`}
                              title="Excluir resultado"
                            >
                              {deletingId === result.id ? <Activity size={15} /> : <Trash2 size={15} />}
                            </button>
                          </div>
                        </td>
                      </tr>
                      {expandedId === result.id && (
                        <tr className="result-detail-row" key={`${result.id}-details`}>
                          <td colSpan={8}>
                            <dl>
                              <div><dt>Modelo</dt><dd>{result.model}</dd></div>
                              <div><dt>Versão</dt><dd>{displayVersion(result.modelVersion)}</dd></div>
                              <div><dt>Completude</dt><dd>{percent(result.inputCompleteness)}</dd></div>
                              <div><dt>Medidas estimadas</dt><dd>{result.missingFeatureCount}</dd></div>
                            </dl>
                            <p>
                              O histórico guarda metadados do resultado, não os valores clínicos enviados ao modelo.
                            </p>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
            <footer className="results-pagination">
              <span>{total} {total === 1 ? "resultado" : "resultados"}</span>
              <div>
                <button type="button" onClick={() => onPageChange(page - 1)} disabled={loading || deletingId !== null || page <= 1} aria-label="Página anterior">
                  <ChevronLeft size={16} />
                </button>
                <strong>Página {page} de {pages}</strong>
                <button type="button" onClick={() => onPageChange(page + 1)} disabled={loading || deletingId !== null || page >= pages} aria-label="Próxima página">
                  <ChevronRight size={16} />
                </button>
              </div>
            </footer>
          </>
        )}
      </section>

      <ConfirmDialog
        open={confirmingClear}
        title="Apagar todo o histórico?"
        description={`Esta ação excluirá permanentemente ${historyTotal} ${historyTotal === 1 ? "resultado" : "resultados"} da sua conta e não poderá ser desfeita.`}
        confirmLabel="Apagar tudo"
        busyLabel="Apagando..."
        busy={clearing}
        onCancel={() => setConfirmingClear(false)}
        onConfirm={confirmClear}
      />

      <ConfirmDialog
        open={Boolean(confirmingDelete)}
        title="Excluir este resultado?"
        description={`O resultado ${confirmingDelete?.patientIdentifier ?? ""} será excluído permanentemente do histórico.`}
        confirmLabel="Excluir resultado"
        busyLabel="Excluindo..."
        busy={deletingId !== null}
        onCancel={() => setConfirmingDelete(null)}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
