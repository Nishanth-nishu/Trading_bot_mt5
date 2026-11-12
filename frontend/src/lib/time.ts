// The backend speaks UTC only. The dashboard shows UTC and IST side by side
// and always labels the zone.

function clock(date: Date, timeZone: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone,
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

export function formatUtc(iso: string): string {
  return `${clock(new Date(iso), "UTC")} UTC`;
}

export function formatIst(iso: string): string {
  return `${clock(new Date(iso), "Asia/Kolkata")} IST`;
}
