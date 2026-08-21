"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { QueryProvider } from "../../components/QueryProvider";
import { AppShell } from "../../components/shell/AppShell";
import { SessionProvider, useSession } from "../../lib/session";

function AuthenticatedArea({ children }: Readonly<{ children: React.ReactNode }>) {
  const { session, restoring } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (!restoring && !session) {
      router.replace("/login");
    }
  }, [restoring, session, router]);

  if (restoring || !session) {
    return (
      <main className="min-h-screen grid place-items-center">
        <p className="text-[13px] font-medium text-muted">Restoring session…</p>
      </main>
    );
  }

  return <AppShell>{children}</AppShell>;
}

export default function AppGroupLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <QueryProvider>
      <SessionProvider>
        <AuthenticatedArea>{children}</AuthenticatedArea>
      </SessionProvider>
    </QueryProvider>
  );
}
