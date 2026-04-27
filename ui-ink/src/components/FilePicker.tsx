// IX-01: @ 파일 픽커 — buffer 안 마지막 @token 을 query 로 받아 file list 에서 substring 매칭.
//   Tab/Enter 로 확정 → 부모가 buffer 의 @token 부분만 절대경로로 치환.
//   SlashPopup 패턴 그대로 — ink-select-input + Tab 확정 + Esc 닫기.
import React from 'react'
import {Box, Text, useInput} from 'ink'
import SelectInput from 'ink-select-input'
import {useFileListStore} from '../store/files.js'

interface SelectItem {
  key?: string
  label: string
  value: string
}

interface FilePickerProps {
  // @ 다음 query 부분 — 예: '@src/foo' 면 query='src/foo'
  query: string
  // Tab/Enter 확정 시 호출 — 절대경로 그대로 전달
  onSelect: (path: string) => void
  // Esc 로 닫기
  onClose: () => void
}

const MAX_CANDIDATES = 12

function fuzzyFilter(files: string[], query: string): string[] {
  if (!query) return files.slice(0, MAX_CANDIDATES)
  const q = query.toLowerCase()
  // 정확 startsWith 우선, 그다음 substring (basename startsWith 도 우대)
  const startsWith: string[] = []
  const basenameStarts: string[] = []
  const includes: string[] = []
  for (const f of files) {
    const lower = f.toLowerCase()
    if (lower.startsWith(q)) {
      startsWith.push(f)
    } else {
      const base = lower.split('/').pop() ?? lower
      if (base.startsWith(q)) basenameStarts.push(f)
      else if (lower.includes(q)) includes.push(f)
    }
    if (startsWith.length >= MAX_CANDIDATES) break
  }
  return [...startsWith, ...basenameStarts, ...includes].slice(0, MAX_CANDIDATES)
}

function shortLabel(path: string): string {
  // 너무 긴 경로는 끝부분 N자만 표시 (단축 + 식별성 균형)
  const MAX = 80
  if (path.length <= MAX) return path
  return '…' + path.slice(-(MAX - 1))
}

export const FilePicker: React.FC<FilePickerProps> = ({query, onSelect, onClose}) => {
  const {files, loaded, request} = useFileListStore((s) => ({
    files: s.files,
    loaded: s.loaded,
    request: s.request,
  }))

  // 첫 진입 시 1회 요청 — 이미 캐시 있으면 noop
  React.useEffect(() => {
    request()
  }, [request])

  const candidates = React.useMemo(() => fuzzyFilter(files, query), [files, query])
  const items: SelectItem[] = candidates.map((p) => ({label: shortLabel(p), value: p}))

  const [highlighted, setHighlighted] = React.useState<string | null>(items[0]?.value ?? null)
  React.useEffect(() => {
    if (items.length === 0) { setHighlighted(null); return }
    const stillExists = items.some((i) => i.value === highlighted)
    if (!stillExists) setHighlighted(items[0]?.value ?? null)
  }, [query])

  useInput((_input, key) => {
    if (key.escape) { onClose(); return }
    if (key.tab && highlighted) { onSelect(highlighted); return }
    if (key.return && highlighted) { onSelect(highlighted) }
  })

  if (!loaded) {
    return (
      <Box borderStyle='round' borderColor='gray' paddingX={1}>
        <Text dimColor>파일 목록 로딩 중…</Text>
      </Box>
    )
  }

  if (items.length === 0) {
    return (
      <Box borderStyle='round' borderColor='gray' paddingX={1}>
        <Text dimColor>일치하는 파일 없음 — &quot;{query}&quot;</Text>
      </Box>
    )
  }

  return (
    <Box flexDirection='column' borderStyle='round' borderColor='magenta' paddingX={1}>
      <SelectInput
        items={items}
        onHighlight={(item: SelectItem) => setHighlighted(item.value)}
        onSelect={(item: SelectItem) => onSelect(item.value)}
      />
      <Text dimColor>Tab 또는 Enter 로 선택 · Esc 닫기 · {candidates.length}/{files.length}</Text>
    </Box>
  )
}
