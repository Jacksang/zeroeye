/**
 * LEGACY COMPATIBILITY BOUNDARY.
 *
 * The AngularJS migration shims were removed from this module. The only
 * remaining exports are native browser utilities still referenced by the
 * generated API client while it is migrated to direct fetch calls.
 */

type Transform = (data: unknown) => BodyInit | unknown;

type HttpConfig = {
  method: string;
  url: string;
  data?: unknown;
  params?: Record<string, string>;
  headers?: Record<string, string>;
  timeout?: number;
  withCredentials?: boolean;
  responseType?: XMLHttpRequestResponseType;
  transformRequest?: Transform[];
  transformResponse?: Transform[];
  xsrfHeaderName?: string;
  xsrfCookieName?: string;
};

type HttpResponse<T> = {
  data: T;
  status: number;
  statusText: string;
  headers: () => Record<string, string>;
  config: HttpConfig;
};

type HttpError = HttpResponse<null> & {
  error: unknown;
};

function appendParams(url: string, params?: Record<string, string>): string {
  if (!params) return url;

  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    searchParams.append(key, value);
  }

  const query = searchParams.toString();
  if (!query) return url;
  return `${url}${url.includes('?') ? '&' : '?'}${query}`;
}

function responseHeaders(response: Response): Record<string, string> {
  const headers: Record<string, string> = {};
  response.headers.forEach((value, key) => {
    headers[key] = value;
  });
  return headers;
}

async function parseResponse(response: Response, responseType?: XMLHttpRequestResponseType): Promise<unknown> {
  if (responseType === 'json') {
    return response.json();
  }

  if (responseType === 'arraybuffer') {
    return response.arrayBuffer();
  }

  if (responseType === 'blob') {
    return response.blob();
  }

  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    return response.json();
  }

  return response.text();
}

function createBody(config: HttpConfig): BodyInit | null {
  if (config.data === undefined) return null;

  let body: BodyInit | unknown = JSON.stringify(config.data);
  for (const transform of config.transformRequest ?? []) {
    body = transform(body);
  }

  return body as BodyInit;
}

export async function $httpLegacy<T>(config: HttpConfig): Promise<HttpResponse<T>> {
  const url = appendParams(config.url, config.params);
  const headers: Record<string, string> = {
    Accept: 'application/json, text/plain, */*',
    ...config.headers,
  };

  if (config.data !== undefined && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json;charset=utf-8';
  }

  const controller = new AbortController();
  const timeoutId = config.timeout
    ? window.setTimeout(() => controller.abort(), config.timeout)
    : undefined;

  try {
    const response = await fetch(url, {
      method: config.method,
      headers,
      body: createBody(config),
      signal: controller.signal,
      credentials: config.withCredentials ? 'include' : 'same-origin',
    });

    let data = await parseResponse(response, config.responseType);
    for (const transform of config.transformResponse ?? []) {
      data = transform(data);
    }

    return {
      data: data as T,
      status: response.status,
      statusText: response.statusText,
      headers: () => responseHeaders(response),
      config,
    };
  } catch (error: unknown) {
    const httpError: HttpError = {
      data: null,
      status: -1,
      statusText: error instanceof Error ? error.message : 'Unknown error',
      headers: () => ({}),
      config,
      error,
    };
    throw httpError;
  } finally {
    if (timeoutId !== undefined) {
      window.clearTimeout(timeoutId);
    }
  }
}

export function legacyToJson(value: unknown): string {
  return JSON.stringify(value, (_key, val: unknown) => (val === undefined ? null : val));
}
