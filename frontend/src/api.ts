export const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8160/api/v1'
export type UserMe={id:string;email:string;full_name:string;organization_id:string|null;role_codes:string[];permission_codes:string[]}
export function token(){return localStorage.getItem('hys_token')}
export function setToken(v:string|null){if(v)localStorage.setItem('hys_token',v);else localStorage.removeItem('hys_token')}
export async function api<T>(path:string, options:RequestInit={}):Promise<T>{
  const headers=new Headers(options.headers); headers.set('Content-Type','application/json'); const t=token(); if(t)headers.set('Authorization',`Bearer ${t}`)
  const res=await fetch(`${API}${path}`,{...options,headers});
  if(!res.ok){let detail='Error de API';try{const b=await res.json();detail=typeof b.detail==='string'?b.detail:JSON.stringify(b.detail)}catch{};throw new Error(detail)}
  if(res.status===204)return undefined as T
  return res.json()
}
export async function login(email:string,password:string){const r=await api<{access_token:string}>('/auth/login',{method:'POST',body:JSON.stringify({email,password})});setToken(r.access_token);return r}

export async function apiBlob(path:string):Promise<Blob>{
  const headers=new Headers(); const t=token(); if(t)headers.set('Authorization',`Bearer ${t}`)
  const res=await fetch(`${API}${path}`,{headers}); if(!res.ok)throw new Error(`Descarga HTTP ${res.status}`); return res.blob()
}
