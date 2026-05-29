export function getAccessToken(): string | null {
  return localStorage.getItem("dd_access_token");
}

export function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getAccessToken();
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  };
}

export function networkFetchError(err: unknown, apiBaseUrl: string): Error {
  const msg = err instanceof Error ? err.message : String(err);
  if (msg === "Failed to fetch" || msg.includes("NetworkError")) {
    return new Error(
      `无法连接 API（当前基址：${apiBaseUrl}）。请确认 Backend 已在 127.0.0.1:8010 运行，并使用 npm run dev 开发服务器（带 /api 代理）。`,
    );
  }
  return err instanceof Error ? err : new Error(msg);
}

export async function deleteRequest(path: string, apiBaseUrl: string, fallbackError: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
  } catch (err: unknown) {
    throw networkFetchError(err, apiBaseUrl);
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || fallbackError);
  }
}

export async function uploadRequest<T>(path: string, apiBaseUrl: string, formData: FormData): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      method: "POST",
      headers: authHeaders(),
      body: formData,
    });
  } catch (err: unknown) {
    throw networkFetchError(err, apiBaseUrl);
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Upload failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}
