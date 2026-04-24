"use client";

import { useEffect, useState } from "react";
import { api, SeasonResult } from "@/lib/api";

export default function SeasonPage() {
  const [results, setResults] = useState<SeasonResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [season] = useState(new Date().getFullYear());

  useEffect(() => {
    api.getSeasonResults(season)
      .then((res) => setResults(res.results))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [season]);

  if (loading) return <div className="text-center py-12 text-gray-500" role="status">Loading season results...</div>;

  return (
    <>
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h1 className="text-2xl font-bold text-green-800">{season} PGA Tour Season Results</h1>
        <p className="text-gray-500 mt-1">{results.length} tournaments completed</p>
      </div>

      <div className="bg-white rounded-lg shadow p-6 overflow-x-auto">
        <table className="w-full text-sm" role="table">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-3 py-2 text-left">Date</th>
              <th className="px-3 py-2 text-left">Tournament</th>
              <th className="px-3 py-2 text-left">Course</th>
              <th className="px-3 py-2 text-left">Location</th>
              <th className="px-3 py-2 text-left">Winner</th>
              <th className="px-3 py-2 text-right">Score</th>
              <th className="px-3 py-2 text-right">Purse</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r, i) => {
              const t = r.tournament;
              const w = r.winner;
              const score = w?.par_relative_score;
              const scoreStr = score != null ? (score > 0 ? `+${score}` : `${score}`) : "-";
              const purse = t.purse ? `$${(t.purse / 1_000_000).toFixed(1)}M` : "-";
              const location = [t.city, t.state].filter(Boolean).join(", ");

              return (
                <tr key={t.id} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                  <td className="px-3 py-2 text-gray-500 whitespace-nowrap">{t.start_date}</td>
                  <td className="px-3 py-2 font-medium">{t.name}</td>
                  <td className="px-3 py-2 text-gray-600">{t.course_name}</td>
                  <td className="px-3 py-2 text-gray-500">{location}</td>
                  <td className="px-3 py-2">
                    {w ? (
                      <span className="text-green-700 font-medium">{w.player_name}</span>
                    ) : (
                      <span className="text-gray-400">In Progress</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right font-mono">{w ? scoreStr : "-"}</td>
                  <td className="px-3 py-2 text-right text-gray-500">{purse}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {results.length === 0 && (
          <p className="text-gray-400 text-center py-4">No tournament results available for this season.</p>
        )}
      </div>
    </>
  );
}
