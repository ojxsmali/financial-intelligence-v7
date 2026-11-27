import type { SupabaseClient } from '@supabase/supabase-js'

/**
 * Accounts are optional. They switch on when VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY are set at build
 * time; without them the site still works fully in guest mode. supabase-js is loaded on demand, so visitors
 * who never sign in don't download it.
 */
const URL = import.meta.env.VITE_SUPABASE_URL as string | undefined
const KEY = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined

export const accountsEnabled = Boolean(URL && KEY)

let client: Promise<SupabaseClient> | null = null
export function getSupabase(): Promise<SupabaseClient> | null {
  if (!accountsEnabled) return null
  client ??= import('@supabase/supabase-js').then(m => m.createClient(URL!, KEY!, {
    auth: { persistSession: true, autoRefreshToken: true, storageKey: 'fip.auth' },
  }))
  return client
}

/** Per-user settings row (table public.fi_settings, owner-only under RLS — see supabase/migrations). */
export type RemoteSettings = {
  watchlist?: string[]
  compare?: string[]
  unit?: string
  years?: number
  lastSeen?: Record<string, string>
  symbol?: string
}

export async function loadRemoteSettings(userId: string): Promise<RemoteSettings | null> {
  const sb = await getSupabase()
  if (!sb) return null
  const { data, error } = await sb.from('fi_settings').select('data').eq('user_id', userId).maybeSingle()
  if (error) throw error
  return (data?.data as RemoteSettings | undefined) ?? null
}

export async function saveRemoteSettings(userId: string, data: RemoteSettings) {
  const sb = await getSupabase()
  if (!sb) return
  const { error } = await sb.from('fi_settings').upsert({ user_id: userId, data, updated_at: new Date().toISOString() })
  if (error) throw error
}
