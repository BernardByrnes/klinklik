"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import type {
  CatalogueImportResult,
  CataloguePreviewResponse,
} from "../../generated/api-client";
import { ApiRequestError, apiRequest, newIdempotencyKey } from "../../lib/api";
import {
  getAuthoritySnapshot,
  isCurrentAuthority,
  protectedQueryKey,
  useAuthoritySnapshot,
  type AuthoritySnapshot,
} from "../../lib/authority";
import { isIntentActive, registerIntent, resolveIntent } from "../../lib/intent-registry";
import { shouldRegisterIntent } from "../../lib/recovery";
import { useSession } from "../../lib/session";
import { Button, Card, CardTitleBar, ErrorBanner } from "../../components/ui";

type ImportMode = "ALL_OR_NOTHING" | "VALID_ROWS_ONLY";
const TEMPLATE_VERSION = "1";
const CATALOGUE_HEADER =
  "category,code,dispensing_unit,dosage_form,generic_name,active,brand_name,controlled,currency,effective_from,pack_description,pack_price,prescription_only,price,strength";
const SYNTHETIC_ROW =
  "MEDICINE,SYNTHETIC-EXAMPLE,TABLET,TABLET,Synthetic Paracetamol,true,Synthetic Brand,false,UGX,2026-01-01,Synthetic strip,,true,100.00,500 mg";

type ImportIntent = Readonly<{
  key: string;
  body: {
    content: string;
    mode: ImportMode;
    template_version: string;
    file_name: string;
    file_hash: string;
  };
  authority: AuthoritySnapshot;
  registryId?: string;
}>;

function errorMessage(error: unknown) {
  if (error instanceof ApiRequestError) {
    const body = error.data as { detail?: string } | null;
    if (body?.detail) return body.detail;
  }
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function isServerConflict(error: unknown) {
  return error instanceof ApiRequestError && (error.status === 400 || error.status === 409);
}

export default function CatalogueImportPanel() {
  const { can, currentFacility } = useSession();
  const authority = useAuthoritySnapshot();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const intentRef = useRef<ImportIntent | null>(null);
  const promiseRef = useRef<Promise<void> | null>(null);

  const [fileName, setFileName] = useState("");
  const [content, setContent] = useState("");
  const [mode, setMode] = useState<ImportMode>("ALL_OR_NOTHING");
  const [preview, setPreview] = useState<CataloguePreviewResponse | null>(null);
  const [result, setResult] = useState<CatalogueImportResult | null>(null);
  const [confirmValidRows, setConfirmValidRows] = useState(false);
  const [reconcile, setReconcile] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  function clearReview() {
    resolveIntent(intentRef.current?.registryId);
    intentRef.current = null;
    setFileName("");
    setContent("");
    setMode("ALL_OR_NOTHING");
    setPreview(null);
    setConfirmValidRows(false);
    setReconcile("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  useEffect(() => {
    clearReview();
    setResult(null);
    setNotice("");
    setError("");
    // A different facility or authority must never inherit a reviewed file.
  }, [authority.epoch, authority.organisationId, authority.facilityId, currentFacility?.id]);

  const previewMutation = useMutation({
    mutationFn: (body: { content: string }) =>
      apiRequest<CataloguePreviewResponse>("/api/v1/inventory/catalogue/import/preview/", {
        method: "POST",
        body: JSON.stringify({ content: body.content, template_version: TEMPLATE_VERSION }),
      }),
    onSuccess: (data) => {
      setPreview(data);
      setReconcile("");
      setError("");
      setConfirmValidRows(false);
    },
    onError: (reason) => {
      setPreview(null);
      setError(errorMessage(reason));
    },
  });

  const importMutation = useMutation({
    mutationFn: (intent: ImportIntent) =>
      apiRequest<CatalogueImportResult>("/api/v1/inventory/catalogue/import/", {
        method: "POST",
        headers: { "Idempotency-Key": intent.key },
        body: JSON.stringify(intent.body),
      }),
    onMutate: (intent) => ({ origin: intent.authority }),
    onSuccess: (data, intent, context) => {
      if (!context || !isCurrentAuthority(context.origin)) {
        setReconcile("Authority changed during import. Refresh the preview before trying again.");
        return;
      }
      resolveIntent(intent.registryId);
      intentRef.current = null;
      setResult(data);
      setNotice(
        `Imported ${data.imported} catalogue row(s); skipped ${data.skipped}; row errors ${data.error_count}.`,
      );
      setError("");
      clearReview();
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("inventory-products") });
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("inventory-stock") });
    },
    onError: (reason, intent, context) => {
      if (!context || !isCurrentAuthority(context.origin)) {
        setReconcile("Authority changed during import. Refresh the preview before trying again.");
      } else if (isServerConflict(reason)) {
        resolveIntent(intent.registryId);
        intentRef.current = null;
        setReconcile("The reviewed file was refused. Refresh the preview before importing again.");
      } else if (shouldRegisterIntent(reason)) {
        if (!isIntentActive(intent.registryId)) {
          const registryId = registerIntent({
            operation: "catalogue-import",
            target: intent.body.file_hash || fileName || "catalogue",
            authority: intent.authority,
            retry: async () => {
              if (!isCurrentAuthority(intent.authority)) return;
              await runImport(intent);
            },
          });
          intentRef.current = { ...intent, registryId };
        }
        setReconcile("The import response is uncertain. Retry this exact key or refresh the preview.");
      } else {
        resolveIntent(intent.registryId);
        intentRef.current = null;
        setError(errorMessage(reason));
      }
    },
  });

  async function runImport(intent: ImportIntent) {
    if (promiseRef.current) return promiseRef.current;
    const promise = importMutation
      .mutateAsync(intent)
      .then(() => undefined)
      .catch(() => undefined)
      .finally(() => {
        if (promiseRef.current === promise) promiseRef.current = null;
      });
    promiseRef.current = promise;
    return promise;
  }

  async function readFile(file: File) {
    setError("");
    setNotice("");
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Choose a .csv catalogue file.");
      return;
    }
    try {
      const decoded = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
      if (!decoded.trim()) {
        setError("That CSV file is empty.");
        return;
      }
      resolveIntent(intentRef.current?.registryId);
      intentRef.current = null;
      setFileName(file.name);
      setContent(decoded);
      setPreview(null);
      setResult(null);
      setConfirmValidRows(false);
      setReconcile("");
    } catch {
      setError("The catalogue file must be strict UTF-8.");
    }
  }

  function startImport() {
    if (!preview || !content || intentRef.current || promiseRef.current) return;
    const intent: ImportIntent = {
      key: newIdempotencyKey("s41-catalogue-import"),
      body: {
        content,
        mode,
        template_version: preview.template_version,
        file_name: fileName,
        file_hash: preview.file_hash,
      },
      authority: getAuthoritySnapshot(),
    };
    intentRef.current = intent;
    setConfirmValidRows(false);
    setError("");
    void runImport(intent);
  }

  function downloadTemplate() {
    const blob = new Blob([CATALOGUE_HEADER + SYNTHETIC_ROW + "\n"], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "catalogue-template-synthetic.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  if (!can("catalogue.import")) return null;

  const importDisabled =
    !preview ||
    !content ||
    Boolean(intentRef.current) ||
    importMutation.isPending ||
    (mode === "ALL_OR_NOTHING" && (preview.row_errors.length > 0 || preview.skipped > 0));

  return (
    <Card data-catalogue-import>
      <CardTitleBar title="Catalogue CSV review" />
      <div className="grid gap-3 px-5 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" onClick={downloadTemplate}>
            Download synthetic template
          </Button>
          <p className="text-[11.5px] font-medium text-muted">
            Up to 512 KiB and 1,000 rows. Review is scoped to {currentFacility?.name ?? "this facility"}.
          </p>
        </div>
        <label className="grid gap-1 text-[12px] font-semibold text-secondary" htmlFor="catalogue-file">
          Catalogue CSV file
          <input
            id="catalogue-file"
            ref={fileInputRef}
            type="file"
            accept=".csv,text/csv"
            aria-label="Catalogue CSV file"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void readFile(file);
            }}
          />
        </label>
        <fieldset className="flex flex-wrap gap-4 text-[12.5px] font-medium text-ink">
          <legend className="mb-1 text-[12px] font-semibold text-secondary">Import mode</legend>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="catalogue-mode"
              checked={mode === "ALL_OR_NOTHING"}
              onChange={() => {
                setMode("ALL_OR_NOTHING");
                setPreview(null);
                setConfirmValidRows(false);
                setReconcile("");
              }}
            />
            All or nothing
          </label>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="catalogue-mode"
              checked={mode === "VALID_ROWS_ONLY"}
              onChange={() => {
                setMode("VALID_ROWS_ONLY");
                setPreview(null);
                setConfirmValidRows(false);
                setReconcile("");
              }}
            />
            Valid rows only
          </label>
        </fieldset>
        <Button
          variant="secondary"
          disabled={!content || previewMutation.isPending}
          onClick={() => previewMutation.mutate({ content })}
        >
          {previewMutation.isPending ? "Reviewing…" : "Preview CSV"}
        </Button>

        {notice ? <p className="text-[12px] font-medium text-ink" role="status">{notice}</p> : null}
        {error ? <ErrorBanner message={error} onDismiss={() => setError("")} /> : null}

        {preview && !confirmValidRows ? (
          <div className="rounded-[12px] border border-line-soft px-3.5 py-3" data-catalogue-preview>
            <p className="text-[12px] font-bold uppercase tracking-wide text-muted">Reviewed file</p>
            <p className="mt-1 text-[12.5px] font-semibold text-ink">
              {fileName} · template {preview.template_version} · {currentFacility?.name ?? "facility"}
            </p>
            <p className="mt-1 text-[12.5px] font-medium text-secondary">
              Accepted {preview.valid_rows} · skipped {preview.skipped} · errors {preview.row_errors.length}
            </p>
            {preview.existing_codes.length ? (
              <p className="mt-1 text-[12px] font-medium text-secondary">
                Already in this facility: {preview.existing_codes.join(", ")}
              </p>
            ) : null}
            {preview.row_errors.length ? (
              <ul className="mt-2 space-y-1" role="alert">
                {preview.row_errors.map((rowError) => (
                  <li key={`${rowError.line}-${rowError.code}`} className="text-[12px] font-medium text-ink">
                    Line {rowError.line}: {rowError.errors.join("; ")}
                  </li>
                ))}
              </ul>
            ) : null}
            <div className="mt-3 flex flex-wrap gap-2">
              {mode === "VALID_ROWS_ONLY" ? (
                <Button
                  disabled={preview.row_errors.length === 0 && preview.skipped === 0}
                  onClick={() => setConfirmValidRows(true)}
                >
                  Review valid rows only
                </Button>
              ) : (
                <Button disabled={importDisabled} onClick={startImport}>
                  {importMutation.isPending ? "Importing…" : "Import catalogue"}
                </Button>
              )}
              <Button variant="secondary" onClick={clearReview}>
                Dismiss review
              </Button>
            </div>
          </div>
        ) : null}

        {preview && confirmValidRows ? (
          <div className="rounded-[12px] border border-accent-orange/30 bg-accent-orange-soft px-3.5 py-3" role="alert">
            <p className="text-[12.5px] font-bold text-ink">Confirm valid rows only</p>
            <p className="mt-1 text-[12px] font-medium text-secondary">
              {preview.valid_rows} eligible row(s) will be imported. {preview.row_errors.length} row(s)
              with errors and {preview.skipped} duplicate(s) already in this facility will be skipped.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button disabled={importDisabled} onClick={startImport}>
                {importMutation.isPending ? "Importing…" : "Confirm valid rows import"}
              </Button>
              <Button variant="secondary" onClick={() => setConfirmValidRows(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : null}

        {reconcile ? (
          <div className="rounded-[12px] border border-accent-orange/30 bg-accent-orange-soft px-3.5 py-3" role="alert" data-catalogue-reconcile>
            <p className="text-[12.5px] font-bold text-ink">{reconcile}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                variant="secondary"
                disabled={!content || previewMutation.isPending}
                onClick={() => previewMutation.mutate({ content })}
              >
                Refresh preview
              </Button>
              {intentRef.current ? (
                <Button
                  variant="secondary"
                  disabled={!isCurrentAuthority(intentRef.current.authority) || importMutation.isPending}
                  onClick={() => void runImport(intentRef.current!)}
                >
                  Retry exact import
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}

        {result ? (
          <div className="rounded-[12px] bg-accent-teal-soft px-3.5 py-3 text-[12.5px] font-medium text-ink" role="status" data-catalogue-result>
            Last import: applied {result.imported}, skipped {result.skipped}, row errors{" "}
            {result.error_count}. {result.row_errors.length ? result.row_errors.map((rowError) => `Line ${rowError.line}: ${rowError.errors.join("; ")}`).join(" · ") : ""}
          </div>
        ) : null}
      </div>
    </Card>
  );
}
