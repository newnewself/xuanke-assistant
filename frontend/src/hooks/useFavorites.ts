import { useCallback, useMemo, useState } from 'react'

const KEY = 'xk_favorites_v1'

function load(): string[] {
  try {
    const raw = localStorage.getItem(KEY)
    const arr = raw ? JSON.parse(raw) : []
    // 只留非空字符串并去重，保持收藏先后顺序
    return Array.isArray(arr) ? Array.from(new Set(arr.filter((x: any) => typeof x === 'string' && x))) : []
  } catch {
    return []
  }
}

export interface FavoritesApi {
  /** 收藏的选课课号（xk_id），按收藏先后排序 */
  ids: string[]
  has: (id: string) => boolean
  /** 批量收藏，返回新收藏的门数（已收藏过的不重复计） */
  add: (ids: string[]) => number
  remove: (ids: string[]) => void
  clear: () => void
}

/** 备选课收藏：与已占时段一致存 localStorage（各浏览器独立）；按 xk_id 去重、保序 */
export function useFavorites(): FavoritesApi {
  const [ids, setIds] = useState<string[]>(load)

  const save = (next: string[]) => {
    setIds(next)
    localStorage.setItem(KEY, JSON.stringify(next))
  }

  const has = useCallback((id: string) => load().includes(id), [])

  const add = useCallback((list: string[]) => {
    const cur = load()
    const next = [...cur]
    let added = 0
    for (const x of list) {
      if (x && !next.includes(x)) { next.push(x); added++ }
    }
    if (added) save(next)
    return added
  }, [])

  const remove = useCallback((list: string[]) => {
    const cur = load()
    const next = cur.filter(x => !list.includes(x))
    if (next.length !== cur.length) save(next)
  }, [])

  const clear = useCallback(() => save([]), [])

  // ids 变化才换新对象，避免无关重渲染；has/add/remove 引用稳定
  return useMemo(() => ({ ids, has, add, remove, clear }), [ids, has, add, remove, clear])
}
