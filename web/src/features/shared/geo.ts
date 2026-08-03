/** Geography display helpers shared by the analytical pages. */

/**
 * Flag emoji from an ISO alpha-2 country code ("DE" -> 🇩🇪).
 * Returns an empty string for anything that is not two ASCII letters,
 * so bad data degrades to no flag rather than mojibake.
 */
export function countryFlag(countryCode: string): string {
  const cc = countryCode.trim().toUpperCase();
  if (!/^[A-Z]{2}$/.test(cc)) {
    return "";
  }
  return String.fromCodePoint(
    ...[...cc].map((char) => 0x1f1e6 + (char.charCodeAt(0) - 65)),
  );
}

/**
 * Human label for a subdomain id when no displayName is provided,
 * e.g. "ci_cd" -> "Ci cd". Purely mechanical — never invents wording.
 */
export function subdomainIdLabel(subdomainId: string): string {
  const text = subdomainId.replace(/_/g, " ").trim();
  return text.length > 0 ? text[0].toUpperCase() + text.slice(1) : subdomainId;
}
