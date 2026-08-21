"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { BrandMark } from "../../components/icons";
import { Button, ErrorBanner, Field, TextInput } from "../../components/ui";
import { QueryProvider } from "../../components/QueryProvider";
import { landingRoute } from "../../lib/roles";
import { SessionProvider, useSession } from "../../lib/session";

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function LoginCard() {
  const { session, signIn, restoring } = useSession();
  const router = useRouter();
  const [username, setUsername] = useState("demo");
  const [password, setPassword] = useState("ClinicopusDemo!2026");
  const [organisationId, setOrganisationId] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!restoring && session) {
      router.replace(landingRoute(session));
    }
  }, [restoring, session, router]);

  useEffect(() => {
    // Marks client hydration; e2e waits for this before interacting.
    document.documentElement.dataset.appReady = "1";
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      const opened = await signIn(username, password, organisationId || undefined);
      router.replace(landingRoute(opened));
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setPending(false);
    }
  }

  return (
    <main
      className="min-h-screen grid place-items-center p-6"
      style={{
        background:
          "radial-gradient(circle at 10% 10%, #F1EDFF 0%, #F8F9FC 42%, #EDF4FF 100%)",
      }}
    >
      <section className="w-full max-w-[440px] bg-white border border-line rounded-[22px] p-8 shadow-elevated">
        <div className="flex items-center gap-3">
          <BrandMark className="h-11 w-11" />
          <div className="leading-tight">
            <div className="text-[17px] font-bold tracking-[0.02em] text-ink">KLINKLIK</div>
            <div className="text-[11.5px] font-medium text-muted">Clinic Management System</div>
          </div>
        </div>

        <p className="mt-8 text-[11px] font-bold tracking-[0.12em] uppercase text-primary-text">Clinic operations</p>
        <h1 className="mt-2 text-[28px] font-bold tracking-[-0.02em] text-ink">Welcome back</h1>
        <p className="mt-1 text-[13.5px] font-medium text-secondary">Sign in to your workspace.</p>

        <form className="mt-7 grid gap-4" onSubmit={submit}>
          <Field label="Username" htmlFor="username">
            <TextInput
              id="username"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          </Field>
          <Field label="Password" htmlFor="password">
            <TextInput
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </Field>
          <Field
            label="Organisation ID"
            htmlFor="organisation"
            hint="Optional on the local demo database; required for PostgreSQL."
          >
            <TextInput
              id="organisation"
              value={organisationId}
              onChange={(event) => setOrganisationId(event.target.value)}
              placeholder="Optional for local SQLite"
            />
          </Field>

          {error ? <ErrorBanner message={error} /> : null}

          <Button type="submit" disabled={pending} className="mt-1 w-full">
            {pending ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <p className="mt-6 text-[12px] font-medium text-muted">
          Local demo: <strong className="text-secondary">demo</strong> / <strong className="text-secondary">ClinicopusDemo!2026</strong>
        </p>
      </section>
    </main>
  );
}

export default function LoginPage() {
  return (
    <QueryProvider>
      <SessionProvider>
        <LoginCard />
      </SessionProvider>
    </QueryProvider>
  );
}
