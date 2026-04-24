/**
 * API client for the PGA Tournament Analysis backend.
 */
const API_BASE = "/api";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`);
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json();
}

export interface Tournament {
  id: string;
  name: string;
  course_name: string;
  city: string | null;
  state: string | null;
  country: string | null;
  par: number | null;
  yardage: number | null;
  start_date: string;
  end_date: string;
  season: number;
  purse: number | null;
}

export interface StatWeight {
  category: string;
  display_name: string;
  weight: number;
  explanation: string;
}

export interface PlayerRanking {
  rank: number;
  player_id: string;
  player_name: string;
  composite_score: number;
  world_ranking: number | null;
  fedex_ranking: number | null;
  stats: Record<string, number>;
  stat_ranks: Record<string, number | null>;
}

export interface StatComparison {
  category: string;
  display_name: string;
  player_value: number | null;
  winner_avg: number | null;
  delta: number | null;
  highlighted: boolean;
  weight: number;
}

export interface PlayerProfile {
  player_id: string;
  player_name: string;
  composite_score: number;
  world_ranking: number | null;
  fedex_ranking: number | null;
  comparison: StatComparison[];
  tournament_id: string;
}

export interface HistoryEntry {
  season: number;
  player_id: string;
  player_name: string;
  position: string;
  total_score: number | null;
  par_relative_score: number | null;
  stats: Record<string, number>;
  stat_ranks: Record<string, number | null>;
}

export interface SeasonResult {
  tournament: Tournament;
  winner: {
    player_id: string;
    player_name: string;
    total_score: number | null;
    par_relative_score: number | null;
  } | null;
}

export const api = {
  getCurrentTournament: () =>
    fetchJson<{ tournament: Tournament | null; message: string | null }>("/tournament/current"),

  getTournamentStats: (id: string) =>
    fetchJson<{ stats: StatWeight[]; tournament_id: string }>(`/tournament/${id}/stats`),

  getTournamentHistory: (id: string) =>
    fetchJson<{ history: HistoryEntry[]; tournament_id: string }>(`/tournament/${id}/history`),

  getSeasonResults: (season: number) =>
    fetchJson<{ season: number; results: SeasonResult[]; total: number }>(`/tournament/season/${season}`),

  getPlayerRankings: (tournamentId: string, limit = 50) =>
    fetchJson<{ rankings: PlayerRanking[]; total: number }>(
      `/players/rankings?tournament_id=${tournamentId}&limit=${limit}`
    ),

  getPlayerProfile: (playerId: string, tournamentId: string) =>
    fetchJson<PlayerProfile>(`/players/${playerId}/profile?tournament_id=${tournamentId}`),

  triggerRefresh: () => fetch(`${API_BASE}/refresh`, { method: "POST" }).then((r) => r.json()),

  getStatus: () => fetchJson<{ status: string; last_refresh: string | null; error: string | null }>("/status"),
};
