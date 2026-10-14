"use client";
import { useCallback, useEffect, useState } from "react";
let csrf = "";
export function setCsrf(token: string) {
  csrf = token;
}
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
type ApiOptions = Omit<RequestInit, "body"> & { body?: unknown };
export async function api<T>(
  path: string,
  options: ApiOptions = {},
): Promise<T> {
  const { body, ...rest } = options;
  const multipart = body instanceof FormData;
  const headers = new Headers(rest.headers);
  if (body && !multipart) headers.set("Content-Type", "application/json");
  if (rest.method && rest.method !== "GET" && csrf)
    headers.set("X-CSRF-Token", csrf);
  const response = await fetch(`/api${path}`, {
    ...rest,
    headers,
    credentials: "include",
    cache: "no-store",
    body: body == null ? undefined : multipart ? body : JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail
              .map((item: { msg?: string }) => item.msg || "Invalid input")
              .join(". ")
          : "The request could not be completed. Please try again.";
    throw new ApiError(message, response.status);
  }
  return payload as T;
}
export function useResource<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api<T>(path));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load.");
    } finally {
      setLoading(false);
    }
  }, [path]);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  return { data, loading, error, refresh };
}
export function money(value: string | number | undefined | null) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}
export function dateTime(value: string) {
  const date = new Date(
    value.endsWith("Z") || /[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`,
  );
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("en-IN", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Asia/Kolkata",
      });
}
