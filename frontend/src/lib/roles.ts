import { ApiSession } from "./api";

/*
 * Role derivation for navigation and landing pages. Frontend gating is UX
 * only — the server enforces capabilities authoritatively on every request.
 */

export type UiRole = "admin" | "reception" | "nurse" | "clinician" | "cashier";

export function uiRole(session: ApiSession): UiRole {
  const templates = session.roles.map((role) => role.template_code);
  if (templates.includes("OWNER_ADMIN")) return "admin";
  if (templates.includes("NURSE_TRIAGE")) return "nurse";
  if (templates.includes("CLINICIAN")) return "clinician";
  if (templates.includes("RECEPTION_CASHIER")) {
    // Reception and cashier share a role template; the department decides
    // the landing workspace (BILLING → cashier, otherwise reception).
    const codes = session.roles
      .filter((role) => role.template_code === "RECEPTION_CASHIER")
      .map((role) => role.department_code);
    if (codes.includes("BILLING")) return "cashier";
    return "reception";
  }
  return "reception";
}

export function landingRoute(session: ApiSession): string {
  switch (uiRole(session)) {
    case "nurse":
      return "/triage";
    case "clinician":
      return "/consultations";
    case "cashier":
      return "/billing";
    default:
      return "/overview";
  }
}

export function roleLabel(session: ApiSession): string {
  switch (uiRole(session)) {
    case "admin":
      return "Administrator";
    case "nurse":
      return "Triage Nurse";
    case "clinician":
      return "Clinician";
    case "cashier":
      return "Cashier";
    default:
      return "Reception";
  }
}
