"use client";

import { useEffect, useState } from "react";
import { api, Tournament, StatWeight, PlayerRanking } from "@/lib/api";
import TournamentHeader from "@/components/TournamentHeader";
import StatImportanceChart from "@/components/StatImportanceChart";
import PlayerRankingsTable from "@/components/PlayerRankingsTable";

export default function Dashboard() {
  const [tournament, setTournament] = useState<Tournament | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [stats, setStats] = useState<StatWeight[]>([]);
  const [rankings, setRankings] = useState<PlayerRanking[]>([]);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [tournamentRes, statusRes] = await Promise.all([
        api.getCurrentTournament(),
        api.getStatus(),
      ]);

      setTournament(tournamentRes.tournament);
      setMessage(tournamentRes.message);
      setLastUpdated(statusRes.last_refresh);

      if (tournamentRes.tournament) {
        const [statsRes, rankingsRes] = await Promise.all([
          api.getTournamentStats(tournamentRes.tournament.id),
          api.getPlayerRankings(tournamentRes.tournament.id),
        ]);
        setStats(statsRes.stats);
        setRankings(rankingsRes.rankings);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load data";
      setError(msg);
      console.error("Failed to load data:", err);
    } finally {
      setLoading(false);
    }
  }

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await api.triggerRefresh();
      // Poll for completion
      const poll = setInterval(async () => {
        const status = await api.getStatus();
        if (status.status !== "running") {
          clearInterval(poll);
          setRefreshing(false);
          loadData();
        }
      }, 3000);
    } catch {
      setRefreshing(false);
    }
  }

  return (
    <>
      <TournamentHeader
        tournament={tournament}
        message={message}
        lastUpdated={lastUpdated}
        onRefresh={handleRefresh}
        refreshing={refreshing}
        loading={loading}
        error={error}
      />
      {stats.length > 0 && <StatImportanceChart stats={stats} />}
      {rankings.length > 0 && (
        <PlayerRankingsTable
          rankings={rankings}
          keyStats={stats.map((s) => ({ category: s.category, weight: s.weight }))}
          tournamentId={tournament?.id}
        />
      )}
    </>
  );
}
