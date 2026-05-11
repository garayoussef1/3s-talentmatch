/**
 * CandidateMatchCard — Fiche candidate enrichie avec rapport de matching
 * Couleurs 3S : Orange #F7941D  |  Bleu marine #1B4F8A
 */
import React, { useState } from "react";
import "./CandidateMatchCard.css";

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────
function pct(v) {
  return v != null ? `${Math.round(v * 100)}%` : "—";
}

function recommLabel(r) {
  const MAP = {
    HAUTEMENT_RECOMMANDE: { label: "Hautement recommandé", color: "#22a05a" },
    RECOMMANDE:           { label: "Recommandé",           color: "#1B4F8A" },
    NEUTRE:               { label: "Neutre",               color: "#888" },
    NON_RECOMMANDE:       { label: "Non recommandé",       color: "#e53935" },
  };
  return MAP[r] || { label: r || "—", color: "#888" };
}

function confidenceLabel(c) {
  const MAP = {
    HAUTE:   { label: "Haute",   color: "#22a05a" },
    MOYENNE: { label: "Moyenne", color: "#F7941D" },
    BASSE:   { label: "Basse",   color: "#e53935" },
  };
  return MAP[c] || { label: c || "—", color: "#888" };
}

// ─────────────────────────────────────────────
// ScoreBar
// ─────────────────────────────────────────────
function ScoreBar({ value, color }) {
  const w = Math.round((value || 0) * 100);
  return (
    <div className="cmcard-bar-track">
      <div
        className="cmcard-bar-fill"
        style={{ width: `${w}%`, background: color || "#1B4F8A" }}
      />
      <span className="cmcard-bar-label">{w}%</span>
    </div>
  );
}

// ─────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────
export default function CandidateMatchCard({ candidate, rank }) {
  const [open, setOpen] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);

  const {
    candidate_name,
    candidate_email,
    hybrid_score,
    heuristic_score,
    bert_score,
    bert_base_score,
    bert_gain,
    report = {},
    ai_summary = {},
  } = candidate;

  const bertRaw = bert_score ?? 0;
  const weights = candidate?.weights || { bert: 0.6, heuristic: 0.4 };
  const hybridRaw = candidate?.hybrid_score ?? ((weights.bert * (bertRaw || 0)) + (weights.heuristic * (heuristic_score || 0)));

  const { label: rl, color: rc } = recommLabel(report.recommendation);
  const { label: cl, color: cc } = confidenceLabel(report.confidence);

  const hasReport = report && Object.keys(report).length > 0 && !report.error;
  const canShowReport = hasReport || (ai_summary?.summary) || (candidate?.bert?.inconsistencies?.length > 0);

  return (
    <div className={`cmcard ${open ? "cmcard--open" : ""}`}>
      {/* ── Header ── */}
      <div className="cmcard-header" onClick={() => setOpen(!open)}>
        <div className="cmcard-rank">#{rank}</div>

        <div className="cmcard-info">
          <span className="cmcard-name">{candidate_name || "—"}</span>
          <span className="cmcard-email">{candidate_email || ""}</span>
        </div>

        <div className="cmcard-scores-row">
          <ScoreScore label="TalentMatch" value={bertRaw}        color="#F7941D" />
          <ScoreScore label="Hybride"     value={hybridRaw}      color="#1B4F8A" />
          <ScoreScore label="Heuristique" value={heuristic_score} color="#888" />
        </div>

        {hasReport && (
          <div className="cmcard-badges">
            <span className="cmcard-badge" style={{ background: rc }}>
              {rl}
            </span>
            <span
              className="cmcard-badge cmcard-badge--outline"
              style={{ borderColor: cc, color: cc }}
            >
              Confiance {cl}
            </span>
          </div>
        )}

        {canShowReport && (
          <button
            className="cmcard-report-btn"
            onClick={(e) => { e.stopPropagation(); setReportOpen(true); }}
          >
            Rapport
          </button>
        )}

        <button className="cmcard-toggle" aria-label="Détail">
          {open ? "▲" : "▼"}
        </button>
      </div>

      {/* ── Detail panel ── */}
      {open && (
        <div className="cmcard-body">
          {/* Barres de scores */}
          <section className="cmcard-section">
            <h4 className="cmcard-section-title">Scores détaillés</h4>
            <div className="cmcard-bars">
              <BarRow label="TalentMatch-BERT"  value={bertRaw}         color="#F7941D" />
              <BarRow label="Score hybride"     value={hybridRaw}       color="#1B4F8A" />
              <BarRow label="Heuristique"       value={heuristic_score} color="#5b8dd9" />
              {bert_base_score != null && (
                <BarRow label="BERT base"       value={bert_base_score} color="#bbb" />
              )}
            </div>
            {bert_gain != null && (
              <p className="cmcard-gain">
                Gain TalentMatch vs base :{" "}
                <strong style={{ color: bert_gain >= 0 ? "#22a05a" : "#e53935" }}>
                  {bert_gain >= 0 ? "+" : ""}{Math.round(bert_gain * 100)} pts
                </strong>
              </p>
            )}
          </section>

          {hasReport && (
            <>
              {/* Explication */}
              {report.explanation && (
                <section className="cmcard-section">
                  <h4 className="cmcard-section-title">Analyse</h4>
                  <p className="cmcard-explanation">{report.explanation}</p>
                </section>
              )}

              {/* Points forts / Manques */}
              <section className="cmcard-section cmcard-two-col">
                <div>
                  <h4 className="cmcard-section-title cmcard-green">
                    Points forts
                  </h4>
                  {report.strong_points?.length > 0 ? (
                    <ul className="cmcard-list">
                      {report.strong_points.map((s, i) => (
                        <li key={i} className="cmcard-list-item cmcard-list-item--green">
                          {s}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="cmcard-muted">Aucun point fort identifié</p>
                  )}
                </div>
                <div>
                  <h4 className="cmcard-section-title cmcard-red">
                    Compétences manquantes
                  </h4>
                  {report.missing_skills?.length > 0 ? (
                    <ul className="cmcard-list">
                      {report.missing_skills.map((s, i) => (
                        <li key={i} className="cmcard-list-item cmcard-list-item--red">
                          {s}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="cmcard-muted">Toutes les compétences clés présentes</p>
                  )}
                </div>
              </section>

              {/* Points faibles */}
              {report.weak_points?.length > 0 && (
                <section className="cmcard-section">
                  <h4 className="cmcard-section-title cmcard-orange">
                    Points d'attention
                  </h4>
                  <ul className="cmcard-list">
                    {report.weak_points.map((s, i) => (
                      <li key={i} className="cmcard-list-item cmcard-list-item--orange">
                        {s}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* Exp / Edu */}
              <section className="cmcard-section cmcard-meta-row">
                <MetaItem
                  label="Expérience"
                  ok={report.experience_match}
                />
                <MetaItem
                  label="Formation"
                  ok={report.education_match}
                />
              </section>

              {/* Action recruteur */}
              {report.action && (
                <section className="cmcard-section cmcard-action">
                  <span className="cmcard-action-icon">💼</span>
                  <span>{report.action}</span>
                </section>
              )}
            </>
          )}

          {/* Résumé matching */}
          {ai_summary?.summary && (
            <section className="cmcard-section cmcard-ai-summary">
              <h4 className="cmcard-section-title">
                Synthèse
                {ai_summary.source === "claude" && (
                  <span className="cmcard-ai-badge">Claude</span>
                )}
              </h4>
              <p>{ai_summary.summary}</p>
            </section>
          )}

          {/* Incohérences */}
          {candidate.bert?.inconsistencies?.length > 0 && (
            <section className="cmcard-section">
              <h4 className="cmcard-section-title cmcard-orange">
                Incohérences détectées
              </h4>
              <ul className="cmcard-list">
                {candidate.bert.inconsistencies.map((inc, i) => (
                  <li key={i} className="cmcard-list-item cmcard-list-item--orange">
                    <strong>{inc.skill}</strong> — {inc.reason}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}

      {reportOpen && (
        <div className="cmcard-modal" onClick={() => setReportOpen(false)}>
          <div className="cmcard-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="cmcard-modal-header">
              <div>
                <div className="cmcard-modal-title">Rapport de matching</div>
                <div className="cmcard-modal-sub">
                  #{rank} · {candidate_name || "—"}
                </div>
              </div>
              <button className="cmcard-modal-close" onClick={() => setReportOpen(false)}>
                ✕
              </button>
            </div>

            <div className="cmcard-modal-body">
              <section className="cmcard-section">
                <h4 className="cmcard-section-title">Résumé</h4>
                <div className="cmcard-modal-kpis">
                  <div className="cmcard-kpi">
                    <span className="cmcard-kpi-label">TalentMatch</span>
                    <span className="cmcard-kpi-val">{pct(bertRaw)}</span>
                  </div>
                  <div className="cmcard-kpi">
                    <span className="cmcard-kpi-label">Hybride</span>
                    <span className="cmcard-kpi-val">{pct(hybridRaw)}</span>
                  </div>
                  <div className="cmcard-kpi">
                    <span className="cmcard-kpi-label">Heuristique</span>
                    <span className="cmcard-kpi-val">{pct(heuristic_score)}</span>
                  </div>
                </div>
                {report?.explanation && (
                  <p className="cmcard-explanation">{report.explanation}</p>
                )}
              </section>

              {hasReport && (
                <section className="cmcard-section cmcard-two-col">
                  <div>
                    <h4 className="cmcard-section-title cmcard-green">Points forts</h4>
                    {report.strong_points?.length > 0 ? (
                      <ul className="cmcard-list">
                        {report.strong_points.map((s, i) => (
                          <li key={i} className="cmcard-list-item cmcard-list-item--green">
                            {s}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="cmcard-muted">Aucun point fort identifié</p>
                    )}
                  </div>
                  <div>
                    <h4 className="cmcard-section-title cmcard-red">Compétences manquantes</h4>
                    {report.missing_skills?.length > 0 ? (
                      <ul className="cmcard-list">
                        {report.missing_skills.map((s, i) => (
                          <li key={i} className="cmcard-list-item cmcard-list-item--red">
                            {s}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="cmcard-muted">Toutes les compétences clés présentes</p>
                    )}
                  </div>
                </section>
              )}

              {report?.weak_points?.length > 0 && (
                <section className="cmcard-section">
                  <h4 className="cmcard-section-title cmcard-orange">Points d'attention</h4>
                  <ul className="cmcard-list">
                    {report.weak_points.map((s, i) => (
                      <li key={i} className="cmcard-list-item cmcard-list-item--orange">
                        {s}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {(report?.experience_match != null || report?.education_match != null) && (
                <section className="cmcard-section cmcard-meta-row">
                  {report?.experience_match != null && (
                    <MetaItem label="Expérience" ok={report.experience_match} />
                  )}
                  {report?.education_match != null && (
                    <MetaItem label="Formation" ok={report.education_match} />
                  )}
                </section>
              )}

              {ai_summary?.summary && (
                <section className="cmcard-section cmcard-ai-summary">
                  <h4 className="cmcard-section-title">
                    Synthèse
                    {ai_summary.source === "claude" && (
                      <span className="cmcard-ai-badge">Claude</span>
                    )}
                  </h4>
                  <p>{ai_summary.summary}</p>
                </section>
              )}

              {candidate?.bert?.inconsistencies?.length > 0 && (
                <section className="cmcard-section">
                  <h4 className="cmcard-section-title cmcard-orange">Incohérences détectées</h4>
                  <ul className="cmcard-list">
                    {candidate.bert.inconsistencies.map((inc, i) => (
                      <li key={i} className="cmcard-list-item cmcard-list-item--orange">
                        <strong>{inc.skill}</strong> — {inc.reason}
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────
function ScoreScore({ label, value, extra, color }) {
  return (
    <div className="cmcard-score-item">
      <span className="cmcard-score-val" style={{ color }}>
        {pct(value)}{extra != null ? ` / ${Math.round(extra * 100)}%` : ''}
      </span>
      <span className="cmcard-score-label">{label}</span>
    </div>
  );
}

function BarRow({ label, value, color }) {
  return (
    <div className="cmcard-bar-row">
      <span className="cmcard-bar-name">{label}</span>
      <ScoreBar value={value} color={color} />
    </div>
  );
}

function MetaItem({ label, ok }) {
  const color = ok ? "#22a05a" : "#e53935";
  const icon  = ok ? "✓" : "✗";
  return (
    <div className="cmcard-meta-item">
      <span className="cmcard-meta-icon" style={{ color }}>{icon}</span>
      <span className="cmcard-meta-label">{label}</span>
    </div>
  );
}
