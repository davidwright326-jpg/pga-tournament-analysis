"use client";

import { Tournament } from "@/lib/api";

export interface TournamentHeaderProps {
  tournament: Tournament | null;
  message?: string | null;
  lastUpdated?: string | null;
  onRefresh?: () => void;
  refreshing?: boolean;
  loading?: boolean;
  error?: string | null;
}

export function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr + "T00:00:00");
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return dateStr;
  }
}

export function buildLocationString(city: string | null, state: string | null): string {
  return [city, state].filter(Boolean).join(", ");
}

export default function TournamentHeader({
  tournament,
  message,
  lastUpdated,
  onRefresh,
  refreshing,
  loading,
  error,
}: TournamentHeaderProps) {
  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6 mb-6 animate-pulse" role="status" aria-label="Loading tournament data">
        <div className="h-7 bg-gray-200 rounded w-1/3 mb-3" />
        <div className="h-5 bg-gray-200 rounded w-1/4 mb-2" />
        <div className="h-4 bg-gray-200 rounded w-1/2 mb-2" />
        <div className="flex gap-4 mt-2">
          <div className="h-4 bg-gray-200 rounded w-16" />
          <div className="h-4 bg-gray-200 rounded w-24" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow p-6 mb-6 border-l-4 border-red-500" role="alert">
        <p className="text-red-700 font-medium">Failed to load tournament data</p>
        <p className="text-red-500 text-sm mt-1">{error}</p>
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={refreshing}
            className="mt-3 px-3 py-1 bg-red-600 text-white rounded hover:bg-red-500 disabled:opacity-50 text-sm"
            aria-label="Retry loading data"
          >
            {refreshing ? "Retrying..." : "Retry"}
          </button>
        )}
      </div>
    );
  }

  if (!tournament) {
    return (
      <div className="bg-white rounded-lg shadow p-6 mb-6" role="status">
        <p className="text-gray-500 text-lg">{message || "No tournament scheduled"}</p>
      </div>
    );
  }

  const location = buildLocationString(tournament.city, tournament.state);

  return (
    <div className="bg-white rounded-lg shadow p-6 mb-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold text-green-800">{tournament.name}</h1>
          <p className="text-gray-600 mt-1">{tournament.course_name}</p>
          <p className="text-sm text-gray-500 mt-1">
            {location && <>{location} &middot; </>}
            {formatDate(tournament.start_date)} &ndash; {formatDate(tournament.end_date)}
          </p>
          <div className="flex gap-4 mt-2 text-sm text-gray-600">
            {tournament.par != null && <span>Par {tournament.par}</span>}
            {tournament.yardage != null && <span>{tournament.yardage.toLocaleString()} yards</span>}
            {tournament.purse != null && <span>Purse: ${(tournament.purse / 1_000_000).toFixed(1)}M</span>}
          </div>
        </div>
        <div className="text-right text-sm text-gray-400">
          {lastUpdated && <p>Updated: {new Date(lastUpdated).toLocaleString()}</p>}
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={refreshing}
              className="mt-2 px-3 py-1 bg-green-700 text-white rounded hover:bg-green-600 disabled:opacity-50"
              aria-label="Refresh data"
            >
              {refreshing ? "Refreshing..." : "Refresh Data"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
