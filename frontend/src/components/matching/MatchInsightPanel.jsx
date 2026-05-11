/**
 * MatchInsightPanel — Radar chart + explication offer-specific + comparaison
 * Toutes les données sont issues du matching pour CETTE offre spécifique.
 */
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Tooltip, Legend,
} from "recharts";
import "./MatchInsightPanel.css";

// ── Couleurs pour la comparaison (jusqu'à 5 candidats) ──────────────────────
const COLORS = ["#F7941D", "#1B4F8A", "#22a05a", "#9b59b6", "#e53935"];

// ── Construit les 5 axes radar à partir des données offer-specific ──────────
function buildRadarAxes(r) {
  const hd = r.heuristic_details?.components || {};
  const bd = r.bert_details || {};
  return [
    { axis: "Compétences", value: Math.round((hd.skills?.score ?? 0) * 100) },
    { axis: "Expérience",  value: Math.round((hd.experience?.score ?? 0) * 100) },
    { axis: "Formation",   value: Math.round((hd.education?.score ?? 0) * 100) },
    { axis: "Sémantique",  value: Math.round((bd.bert_semantic ?? r.bert_score ?? 0) * 100) },
    { axis: "Localisation",value: Math.round((hd.location?.score ?? 0) * 100) },
  ];
}

// ── Génère les phrases explicatives spécifiques à l'offre ───────────────────
function buildExplanationLines(r, offerTitle) {
  const hd  = r.heuristic_details?.components || {};
  const exp = hd.experience || {};
  const edu = hd.education  || {};
  const sk  = hd.skills     || {};

  const matched = (sk.matched || []).filter(m => (m.ratio ?? 0) >= 0.6).length;
  const total   = (sk.matched || []).length;
  const missing = r.report?.missing_skills || [];
  const strong  = r.report?.strong_points  || [];
  const lines   = [];

  // Compétences — spécifique à l'offre
  if (total > 0) {
    const pct = Math.round((matched / total) * 100);
    lines.push({
      icon: pct >= 70 ? "✅" : pct >= 40 ? "⚠️" : "❌",
      text: `${matched}/${total} compétences requises pour « ${offerTitle} » (${pct}%)`,
      color: pct >= 70 ? "#22a05a" : pct >= 40 ? "#F7941D" : "#e53935",
    });
  }

  // Expérience — années vs exigences de l'offre
  if (exp.candidate_years != null && exp.required_years != null) {
    const ok = exp.candidate_years >= exp.required_years;
    lines.push({
      icon: ok ? "✅" : "⚠️",
      text: `${exp.candidate_years} ans d'expérience (${exp.required_years} requis pour ce poste)`,
      color: ok ? "#22a05a" : "#F7941D",
    });
  }

  // Formation — niveau vs exigences de l'offre
  if (edu.candidate_level != null && edu.required_level != null) {
    const ok = edu.candidate_level >= edu.required_level;
    lines.push({
      icon: ok ? "✅" : "⚠️",
      text: `Bac+${edu.candidate_level} (Bac+${edu.required_level} requis pour ce poste)`,
      color: ok ? "#22a05a" : "#F7941D",
    });
  }

  // Localisation
  if (hd.location?.score != null) {
    lines.push({
      icon: hd.location.score === 1 ? "📍" : "📍",
      text: hd.location.score === 1 ? "Localisation compatible" : "Localisation non confirmée",
      color: hd.location.score === 1 ? "#22a05a" : "#888",
    });
  }

  // Points manquants — spécifiques à l'offre
  if (missing.length > 0) {
    lines.push({
      icon: "🔴",
      text: `Manque pour ce poste : ${missing.slice(0, 4).join(", ")}${missing.length > 4 ? "…" : ""}`,
      color: "#e53935",
    });
  }

  // Points forts — spécifiques à l'offre
  if (strong.length > 0) {
    lines.push({
      icon: "⭐",
      text: strong.slice(0, 2).join(" · "),
      color: "#1B4F8A",
    });
  }

  return lines;
}

// ── Composant radar d'un seul candidat ──────────────────────────────────────
function SingleRadar({ result, color = "#F7941D" }) {
  const axes = buildRadarAxes(result);
  return (
    <ResponsiveContainer width="100%" height={220}>
      <RadarChart data={axes} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
        <PolarGrid stroke="#e0e7ff" />
        <PolarAngleAxis dataKey="axis" tick={{ fontSize: 11, fill: "#444" }} />
        <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
        <Radar
          name={result.candidate_name || "Candidat"}
          dataKey="value"
          stroke={color}
          fill={color}
          fillOpacity={0.25}
          strokeWidth={2}
        />
        <Tooltip formatter={(v) => `${v}%`} />
      </RadarChart>
    </ResponsiveContainer>
  );
}

// ── Radar de comparaison multi-candidats ─────────────────────────────────────
function CompareRadar({ results }) {
  // Fusionner les axes en un seul tableau multi-séries
  const axes = ["Compétences", "Expérience", "Formation", "Sémantique", "Localisation"];
  const data = axes.map((axis, i) => {
    const row = { axis };
    results.forEach((r, ri) => {
      row[`c${ri}`] = buildRadarAxes(r)[i].value;
    });
    return row;
  });

  return (
    <ResponsiveContainer width="100%" height={280}>
      <RadarChart data={data} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
        <PolarGrid stroke="#e0e7ff" />
        <PolarAngleAxis dataKey="axis" tick={{ fontSize: 11, fill: "#444" }} />
        <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
        {results.map((r, i) => (
          <Radar
            key={r.candidate_id}
            name={r.candidate_name || `Candidat ${i + 1}`}
            dataKey={`c${i}`}
            stroke={COLORS[i % COLORS.length]}
            fill={COLORS[i % COLORS.length]}
            fillOpacity={0.18}
            strokeWidth={2}
          />
        ))}
        <Legend iconSize={10} wrapperStyle={{ fontSize: 12 }} />
        <Tooltip formatter={(v) => `${v}%`} />
      </RadarChart>
    </ResponsiveContainer>
  );
}

// ── Panel principal (mode single) ────────────────────────────────────────────
export function MatchInsightPanel({ result, offerTitle, color = "#F7941D" }) {
  const lines = buildExplanationLines(result, offerTitle);
  const rec   = result.report?.recommendation;
  const recMap = {
    HAUTEMENT_RECOMMANDE: { label: "Hautement recommandé",  bg: "#d4edda", color: "#22a05a" },
    RECOMMANDE:           { label: "Recommandé",            bg: "#dce8fb", color: "#1B4F8A" },
    NEUTRE:               { label: "Neutre",                bg: "#f5f5f5", color: "#888" },
    NON_RECOMMANDE:       { label: "Non recommandé",        bg: "#fde8e8", color: "#e53935" },
  };
  const badge = recMap[rec];

  return (
    <div className="mip-root">
      <div className="mip-header">
        <span className="mip-title">Analyse pour « {offerTitle} »</span>
        {badge && (
          <span className="mip-badge" style={{ background: badge.bg, color: badge.color }}>
            {badge.label}
          </span>
        )}
      </div>

      <div className="mip-body">
        {/* Radar */}
        <div className="mip-radar">
          <SingleRadar result={result} color={color} />
        </div>

        {/* Explication offer-specific */}
        <div className="mip-explain">
          <div className="mip-explain-title">Pourquoi ce candidat pour ce poste ?</div>
          {lines.length === 0 ? (
            <p className="mip-no-data">Données insuffisantes pour générer une analyse.</p>
          ) : (
            <ul className="mip-lines">
              {lines.map((l, i) => (
                <li key={i} className="mip-line">
                  <span className="mip-line-icon">{l.icon}</span>
                  <span className="mip-line-text" style={{ color: l.color }}>{l.text}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Panel de comparaison (mode multi) ────────────────────────────────────────
export function MatchComparePanel({ results, offerTitle, onClose }) {
  if (!results || results.length < 2) return null;

  return (
    <div className="mcp-root">
      <div className="mcp-header">
        <span className="mcp-title">Comparaison pour « {offerTitle} »</span>
        <button className="mcp-close" onClick={onClose}>✕ Fermer</button>
      </div>

      <CompareRadar results={results} />

      <div className="mcp-table">
        <table>
          <thead>
            <tr>
              <th>Critère</th>
              {results.map((r, i) => (
                <th key={r.candidate_id} style={{ color: COLORS[i % COLORS.length] }}>
                  {r.candidate_name || `Candidat ${i + 1}`}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {["Compétences", "Expérience", "Formation", "Sémantique", "Localisation"].map((axis, i) => (
              <tr key={axis}>
                <td className="mcp-axis">{axis}</td>
                {results.map((r) => {
                  const val = buildRadarAxes(r)[i].value;
                  return (
                    <td key={r.candidate_id} className="mcp-val">
                      <div className="mcp-bar-wrap">
                        <div
                          className="mcp-bar"
                          style={{
                            width: `${val}%`,
                            background: val >= 70 ? "#22a05a" : val >= 40 ? "#F7941D" : "#e53935",
                          }}
                        />
                        <span>{val}%</span>
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
            <tr className="mcp-row-hybrid">
              <td className="mcp-axis">Score global</td>
              {results.map((r) => {
                const w = r.weights || { bert: 0.6, heuristic: 0.4 };
                const h = Math.round(((w.bert * (r.bert_score || 0)) + (w.heuristic * (r.heuristic_score || 0))) * 100);
                return (
                  <td key={r.candidate_id} className="mcp-val mcp-val-bold">{h}%</td>
                );
              })}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
