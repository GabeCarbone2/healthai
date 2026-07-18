const SHORT_DATE_FORMATTER = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

const LONG_DATE_FORMATTER = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "long",
});

const TIME_FORMATTER = new Intl.DateTimeFormat("pt-BR", {
  hour: "2-digit",
  minute: "2-digit",
});

function parseDate(value: string) {
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (dateOnly) {
    const [, year, month, day] = dateOnly;
    return new Date(Number(year), Number(month) - 1, Number(day));
  }
  return new Date(value);
}

export function formatBrazilianDate(
  value: string | null | undefined,
  style: "short" | "long" = "short",
) {
  if (!value) return "Data não registrada";
  const date = parseDate(value);
  if (Number.isNaN(date.getTime())) return "Data não registrada";
  return style === "long"
    ? LONG_DATE_FORMATTER.format(date)
    : SHORT_DATE_FORMATTER.format(date);
}

export function formatBrazilianDateTime(value: string) {
  const date = parseDate(value);
  if (Number.isNaN(date.getTime())) return "Data não registrada";
  return `${SHORT_DATE_FORMATTER.format(date)} às ${TIME_FORMATTER.format(date)}`;
}

export function isoDateToBrazilian(value: string) {
  if (!value) return "";
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  return match ? `${match[3]}/${match[2]}/${match[1]}` : "";
}

export function brazilianDateToIso(value: string) {
  if (!value.trim()) return "";
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value.trim());
  if (!match) return null;
  const [, day, month, year] = match;
  const date = new Date(Number(year), Number(month) - 1, Number(day));
  if (
    date.getFullYear() !== Number(year)
    || date.getMonth() !== Number(month) - 1
    || date.getDate() !== Number(day)
  ) {
    return null;
  }
  return `${year}-${month}-${day}`;
}

export function maskBrazilianDateInput(value: string) {
  const digits = value.replace(/\D/g, "").slice(0, 8);
  if (digits.length <= 2) return digits;
  if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
}
