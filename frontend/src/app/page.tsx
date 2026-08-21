"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { QueryProvider } from "../components/QueryProvider";
import { landingRoute } from "../lib/roles";
import { SessionProvider, useSession } from "../lib/session";

function RootRedirect() {
  const { session, restoring } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (restoring) return;
    router.replace(session ? landingRoute(session) : "/login");
  }, [restoring, session, router]);

  return (
    <main className="min-h-screen grid place-items-center">
      <p className="text-[13px] font-medium text-muted">Loading KlinKlik…</p>
    </main>
  );
}

export default function HomePage() {
  return (
    <QueryProvider>
      <SessionProvider>
        <RootRedirect />
      </SessionProvider>
    </QueryProvider>
  );
}
