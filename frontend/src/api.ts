export type Meal = { key: string; title: string; earliest_start: string; latest_end: string; duration_minutes: number }
export type Preferences = { wake_time: string; sleep_time: string; timezone: string; meals: Meal[] }
export type Activity = {
  id: number; title: string; description: string; category: Category; duration_minutes: number; priority: number;
  required: boolean; earliest_start: string; latest_end: string; recurrence: 'daily'|'weekdays'|'weekends'|'once'; target_date: string|null; enabled: boolean
}
export type Category = 'work'|'study'|'health'|'personal'|'leisure'
export type Event = { id: number; title: string; on_date: string; start_time: string; end_time: string; source: string }
export type Block = { id: number; kind: 'event'|'activity'|'meal'; source_id: number|null; title: string; category: Category; start_min: number; end_min: number; status: 'pending'|'done'|'skipped'; explanation: string }
export type Plan = { id: number; on_date: string; warnings: string[]; blocks: Block[] }
export type PlanProposal = {
  on_date: string; revision: string; warnings: string[]; calendar_stale: boolean;
  blocks: Omit<Block,'id'>[]; changes: {title:string;kind:'added'|'removed'|'moved';before:[number,number]|null;after:[number,number]|null}[];
}


export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try { response = await fetch(`/api${path}`, { ...init, headers: { 'Content-Type':'application/json', ...init.headers } }) }
  catch { throw new Error('Не вдалося з’єднатися із сервером. Переконайтеся, що FastAPI запущено.') }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    const detail = payload.detail
    const info = Array.isArray(detail) ? detail.map((d: {msg: string}) => d.msg).join('; ') : detail
    throw new Error(typeof info === 'string' ? info : `Помилка сервера (${response.status})`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
export const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) })
export const minuteLabel = (min: number): string => `${String(Math.floor(min/60)).padStart(2, '0')}:${String(min%60).padStart(2, '0')}`
export const ukDate = (date: string) => new Intl.DateTimeFormat('uk-UA', {day:'numeric',month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(date+'T12:00:00Z'))
export const currentLocalDay = () => new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Kyiv', year:'numeric', month:'2-digit', day:'2-digit' }).format(new Date())
