import { archiveRoot } from "../config/hosting";

type Item = Record<string, unknown>;
type Snapshot = Record<string, unknown>;
let snapshot: Promise<Snapshot> | undefined;

export async function archiveRequest(path: string): Promise<unknown> {
  snapshot ||= fetch(`${archiveRoot}/snapshot.json`).then(async response => {
    if (!response.ok) throw new Error("Saved reports could not be loaded. Refresh and try again.");
    return response.json() as Promise<Snapshot>;
  }).catch(error => { snapshot = undefined; throw error; });
  const data = await snapshot;
  const url = new URL(path, "https://archive.invalid");
  const value = data[url.pathname];
  if (value === undefined) throw new Error("This item is not included in the public report archive.");
  if (Array.isArray(value)) {
    let items = value as Item[];
    const search = (url.searchParams.get("search") || "").toLowerCase();
    if (search) items = items.filter(item => JSON.stringify(item).toLowerCase().includes(search));
    for (const key of ["status", "category", "recording_id", "group_id", "flaw_type", "speaker_id", "split"]) {
      const filter = url.searchParams.get(key);
      if (filter) items = items.filter(item => String(item[key] ?? "") === filter);
    }
    const offset = Math.max(0, Number(url.searchParams.get("offset")) || 0);
    const limit = Math.min(100, Math.max(1, Number(url.searchParams.get("limit")) || 20));
    return { items: items.slice(offset, offset + limit), total: items.length, offset, limit };
  }
  return structuredClone(value);
}
