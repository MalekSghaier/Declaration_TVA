import axios from "axios";

let accessToken: string | null = null;

export const setAccessToken = (t: string | null) => {
  accessToken = t;
};

export const api = axios.create({
  baseURL: "/api",
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }

  return config;
});

export async function fetchFileBlobUrl(path: string): Promise<string> {
  const res = await api.get(path, { responseType: "blob" });
  return URL.createObjectURL(res.data);
}