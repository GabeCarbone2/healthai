import {
  Activity,
  CheckCircle2,
  ExternalLink,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";

import { fetchCrmReviews, reviewCrm } from "../api";
import type { AdminCrmReview, CrmStatus } from "../types";
import { formatBrazilianDate } from "../utils/date";

const STATUS_LABELS: Record<CrmStatus, string> = {
  pending: "Pendente",
  approved: "Aprovado",
  rejected: "Rejeitado",
};

export function AdminCrmPage() {
  const [filter, setFilter] = useState<CrmStatus>("pending");
  const [reviews, setReviews] = useState<AdminCrmReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [reviewingId, setReviewingId] = useState<number | null>(null);
  const [rejectionId, setRejectionId] = useState<number | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");
  const [error, setError] = useState("");

  async function load(status = filter) {
    setLoading(true);
    setError("");
    try {
      setReviews(await fetchCrmReviews(status));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar as análises.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(filter);
  }, [filter]);

  async function decide(
    review: AdminCrmReview,
    status: "approved" | "rejected",
  ) {
    setReviewingId(review.id);
    setError("");
    try {
      await reviewCrm(
        review.id,
        status,
        status === "rejected" ? rejectionReason : undefined,
      );
      setRejectionId(null);
      setRejectionReason("");
      await load();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível registrar a análise.",
      );
    } finally {
      setReviewingId(null);
    }
  }

  return (
    <div className="page admin-crm-page">
      <header className="page-header">
        <div>
          <h1>Verificação de CRM</h1>
          <p>Análise manual dos cadastros profissionais.</p>
        </div>
        <a
          className="cfm-link"
          href="https://portal.cfm.org.br/busca-medicos/"
          target="_blank"
          rel="noreferrer"
        >
          Consultar no CFM
          <ExternalLink size={15} />
        </a>
      </header>

      <div className="review-filters" aria-label="Filtrar análises">
        {(["pending", "approved", "rejected"] as CrmStatus[]).map(
          (status) => (
            <button
              type="button"
              className={filter === status ? "active" : ""}
              aria-pressed={filter === status}
              onClick={() => setFilter(status)}
              key={status}
            >
              {STATUS_LABELS[status]}
            </button>
          ),
        )}
      </div>

      {error && <div className="form-error" role="alert">{error}</div>}

      {loading ? (
        <div className="loading-state compact">
          <Activity size={22} />
          <span>Carregando análises...</span>
        </div>
      ) : reviews.length === 0 ? (
        <div className="review-empty">
          <ShieldCheck size={28} />
          <h2>Nenhum cadastro {STATUS_LABELS[filter].toLowerCase()}</h2>
          <button type="button" onClick={() => void load()}>
            <RefreshCw size={15} />
            Atualizar
          </button>
        </div>
      ) : (
        <div className="review-list">
          {reviews.map((review) => (
            <article className="review-card" key={review.id}>
              <div className="review-identity">
                <span>{review.name.slice(0, 1).toUpperCase()}</span>
                <div>
                  <h2>{review.name}</h2>
                  <p>{review.email}</p>
                </div>
              </div>
              <dl>
                <div>
                  <dt>Registro</dt>
                  <dd>CRM {review.crm}/{review.crm_uf}</dd>
                </div>
                <div>
                  <dt>E-mail</dt>
                  <dd>
                    {review.email_verified_at
                      ? "Confirmado"
                      : "Não confirmado"}
                  </dd>
                </div>
                <div>
                  <dt>Cadastro</dt>
                  <dd>{formatBrazilianDate(review.created_at)}</dd>
                </div>
              </dl>
              {review.crm_rejection_reason && (
                <p className="review-reason">
                  Motivo: {review.crm_rejection_reason}
                </p>
              )}
              {filter === "pending" && (
                <div className="review-actions">
                  {rejectionId === review.id ? (
                    <label>
                      <span>Motivo da rejeição</span>
                      <textarea
                        required
                        maxLength={500}
                        value={rejectionReason}
                        onChange={(event) =>
                          setRejectionReason(event.target.value)
                        }
                      />
                      <div>
                        <button
                          type="button"
                          onClick={() => {
                            setRejectionId(null);
                            setRejectionReason("");
                          }}
                        >
                          Cancelar
                        </button>
                        <button
                          type="button"
                          className="reject"
                          disabled={
                            !rejectionReason.trim()
                            || reviewingId === review.id
                          }
                          onClick={() => void decide(review, "rejected")}
                        >
                          <XCircle size={15} />
                          Confirmar rejeição
                        </button>
                      </div>
                    </label>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="approve"
                        disabled={reviewingId === review.id}
                        onClick={() => void decide(review, "approved")}
                      >
                        <CheckCircle2 size={16} />
                        Aprovar
                      </button>
                      <button
                        type="button"
                        className="reject"
                        disabled={reviewingId === review.id}
                        onClick={() => setRejectionId(review.id)}
                      >
                        <XCircle size={16} />
                        Rejeitar
                      </button>
                    </>
                  )}
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
