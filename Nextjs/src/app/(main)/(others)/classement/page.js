"use client";

import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faCrown } from "@fortawesome/free-solid-svg-icons";

export default function ClassementPage() {
  const { data: session, status } = useSession();
  const [topUsers, setTopUsers] = useState([]);
  const [userRank, setUserRank] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_FLASK_API_URL || 'http://localhost:5000';

  useEffect(() => {
    async function fetchClassement() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${API_URL}/api/classement/top10`);
        if (!res.ok) throw new Error("Impossible de charger le top 10");
        const data = await res.json();
        setTopUsers(data.top10 || []);

        if (session?.user?.id) {
          const resRank = await fetch(`${API_URL}/api/classement/user/${session.user.id}`);
          if (!resRank.ok) throw new Error("Impossible de charger votre rang");
          const dataRank = await resRank.json();
          setUserRank(dataRank.rank);
        }
      } catch (e) {
        console.error('Erreur lors du fetch du classement:', e);
        setError("Le classement est temporairement indisponible.");
        setTopUsers([]);
        setUserRank(null);
      }
      setLoading(false);
    }
    if (status === "authenticated") fetchClassement();
  }, [session, status, API_URL]);

  if (status === "loading" || loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#111]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#90EE90]"></div>
      </div>
    );
  }

  const gold = "#FFD700";
  const silver = "#C0C0C0";
  const bronze = "#CD7F32";
  const green = "#90EE90";
  const podium = topUsers.slice(0, 3);
  const others = topUsers.slice(3);

  return (
    <div className="min-h-screen bg-[#111] text-white">
      <main className="mx-auto w-full max-w-3xl px-3 py-8 sm:px-5 sm:py-12">
        <section className="mb-8 rounded-2xl border border-[#2a2a2a] bg-[#1a1a1a] p-5 sm:p-6">
          <h1 className="text-3xl font-extrabold tracking-tight text-[#90EE90] sm:text-4xl">
             Classement des utilisateurs
          </h1>
          <p className="mt-2 text-sm text-gray-400 sm:text-base">
            Les 10 profils les plus suivis de la plateforme.
          </p>
          <p className="mt-3 text-sm text-gray-400">Votre position actuelle: <span className="font-semibold text-[#90EE90]">{userRank?.rank || "-"}</span></p>
        </section>

        <section className="rounded-2xl border border-[#2a2a2a] bg-[#1a1a1a] p-5 sm:p-7">
          <h2 className="mb-8 text-center text-xl font-bold text-[#90EE90] sm:text-2xl">Top 10 des plus suivis</h2>

          {error && (
            <div className="mb-6 rounded-xl border border-red-400/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          )}

          {!error && topUsers.length === 0 && (
            <div className="mb-6 rounded-xl border border-[#2f3548] bg-[#151515] px-4 py-6 text-center text-gray-300">
              Aucun utilisateur classé pour le moment.
            </div>
          )}

          <div className="mb-10 flex items-end justify-center gap-2 sm:gap-10">
            {podium[1] && (
              <div className="relative z-10 flex w-24 flex-col items-center sm:w-32">
                {session?.user?.id === podium[1].id && (
                  <span className="absolute -top-7 rounded-full bg-[#90EE90] px-2 py-0.5 text-xs font-bold text-[#181c24] shadow">Vous</span>
                )}
                <img
                  src={podium[1].profile_picture || "/defaultuserpfp.png"}
                  alt={podium[1].pseudo}
                  className="mb-2 h-16 w-16 rounded-full border-4 object-cover sm:h-20 sm:w-20"
                  style={{ borderColor: silver, background: "#23272f" }}
                />
                <div className="flex h-20 w-12 items-end justify-center rounded-t-lg border-b-4 shadow-md sm:h-24 sm:w-16" style={{ background: silver, borderBottomColor: "#a8a8a8" }} />
                <span className="mt-2 max-w-[85px] truncate text-center font-semibold" style={{ color: session?.user?.id === podium[1].id ? green : undefined }}>
                  {podium[1].pseudo}
                </span>
                <span className="text-xs text-gray-400">{podium[1].followers_count} followers</span>
              </div>
            )}

            {podium[0] && (
              <div className="relative z-20 flex w-28 flex-col items-center sm:w-40">
                {session?.user?.id === podium[0].id && (
                  <span className="absolute -top-7 rounded-full bg-[#90EE90] px-2 py-0.5 text-xs font-bold text-[#181c24] shadow">Vous</span>
                )}
                <FontAwesomeIcon icon={faCrown} className="mb-2 text-3xl" style={{ color: gold }} />
                <img
                  src={podium[0].profile_picture || "/defaultuserpfp.png"}
                  alt={podium[0].pseudo}
                  className="mb-2 h-24 w-24 rounded-full border-4 object-cover sm:h-28 sm:w-28"
                  style={{ borderColor: gold, background: "#23272f" }}
                />
                <div className="flex h-28 w-16 items-end justify-center rounded-t-lg border-b-4 shadow-lg sm:h-36 sm:w-20" style={{ background: gold, borderBottomColor: "#bfa900" }} />
                <span className="mt-2 max-w-[110px] truncate text-center font-semibold" style={{ color: session?.user?.id === podium[0].id ? green : gold }}>
                  {podium[0].pseudo}
                </span>
                <span className="text-xs text-gray-400">{podium[0].followers_count} followers</span>
              </div>
            )}

            {podium[2] && (
              <div className="relative z-10 flex w-20 flex-col items-center sm:w-28">
                {session?.user?.id === podium[2].id && (
                  <span className="absolute -top-7 rounded-full bg-[#90EE90] px-2 py-0.5 text-xs font-bold text-[#181c24] shadow">Vous</span>
                )}
                <img
                  src={podium[2].profile_picture || "/defaultuserpfp.png"}
                  alt={podium[2].pseudo}
                  className="mb-2 h-14 w-14 rounded-full border-4 object-cover sm:h-16 sm:w-16"
                  style={{ borderColor: bronze, background: "#23272f" }}
                />
                <div className="flex h-16 w-10 items-end justify-center rounded-t-lg border-b-4 shadow-md sm:h-20 sm:w-12" style={{ background: bronze, borderBottomColor: "#8c5a2b" }} />
                <span className="mt-2 max-w-[70px] truncate text-center font-semibold" style={{ color: session?.user?.id === podium[2].id ? green : bronze }}>
                  {podium[2].pseudo}
                </span>
                <span className="text-xs text-gray-400">{podium[2].followers_count} followers</span>
              </div>
            )}
          </div>

          <ol className="space-y-3">
            {others.map((user, idx) => (
              <li
                key={user.id}
                className={`flex items-center justify-between rounded-xl border px-4 py-3 ${
                  session?.user?.id === user.id
                    ? "border-[#90EE90] bg-[#90EE90]/15"
                    : "border-[#2f3548] bg-[#151515]"
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className="w-8 text-center text-xl font-bold text-[#90EE90]">{idx + 4}</span>
                  <img
                    src={user.profile_picture || "/defaultuserpfp.png"}
                    alt={user.pseudo}
                    className="h-10 w-10 rounded-full border border-[#90EE90] object-cover"
                  />
                  <span className="max-w-[130px] truncate font-semibold" style={{ color: session?.user?.id === user.id ? green : undefined }}>
                    {user.pseudo}
                  </span>
                </div>
                <span className="text-sm font-bold text-[#90EE90] sm:text-base">{user.followers_count} followers</span>
              </li>
            ))}
          </ol>
        </section>

        {userRank && userRank.rank > 10 && (
          <section className="mt-8 rounded-2xl border border-[#90EE90]/70 bg-[#121a14] p-5 sm:p-6">
            <h3 className="mb-3 text-center text-lg font-bold text-[#90EE90] sm:text-xl">Votre classement</h3>
            <div className="flex items-center justify-center gap-3">
              <span className="text-2xl font-extrabold text-[#90EE90]">#{userRank.rank}</span>
              <img
                src={userRank.profile_picture || "/defaultuserpfp.png"}
                alt={userRank.pseudo}
                className="h-10 w-10 rounded-full border border-[#90EE90] object-cover"
              />
              <span className="font-semibold" style={{ color: green }}>{userRank.pseudo}</span>
            </div>
            <p className="mt-2 text-center text-sm font-bold text-[#90EE90] sm:text-base">{userRank.followers_count} followers</p>
          </section>
        )}
      </main>
    </div>
  );
}