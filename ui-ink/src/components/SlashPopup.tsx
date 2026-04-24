// SlashPopup — '/' 로 시작하는 buffer 에 대해 command 목록을 보여주는 팝업
// INPT-06: ink-select-input 기반, 실시간 필터, ↑↓ 네비, Tab 으로 확정, Esc 로 닫기
// NOTE: Enter 는 MultilineInput 의 submit 경로로 통과시켜야 하므로
//       Tab 을 확정 키, Esc 를 닫기 키로 사용.
//       onHighlight prop 으로 highlighted item 을 추적한 뒤 Tab 에서 onSelect 호출.
import React from 'react'
import {Box, Text, useInput} from 'ink'
import SelectInput from 'ink-select-input'
import {filterSlash} from '../slash-catalog.js'

// ink-select-input 의 Item 타입 — SelectInput.d.ts 와 동일 구조
interface SelectItem {
  key?: string
  label: string
  value: string
}

interface SlashPopupProps {
  // buffer 의 슬래시 query 부분 — 예: buffer='/hel' → query='/hel'
  // filterSlash 가 내부적으로 leading '/' 를 제거하여 처리함
  query: string
  // Tab 확정 시 호출 — commandName 은 leading slash 포함 ('/help')
  onSelect: (commandName: string) => void
  // Esc 로 닫기
  onClose: () => void
}

// slash-catalog 의 name 은 leading slash 없음 (예: 'help')
// 표시 및 onSelect 에서 leading slash 를 붙여서 일관성 유지
const toItems = (commands: ReturnType<typeof filterSlash>): SelectItem[] =>
  commands.map((c) => ({
    label: '/' + c.name + '  ' + c.summary,
    value: '/' + c.name,
  }))

export const SlashPopup: React.FC<SlashPopupProps> = ({query, onSelect, onClose}) => {
  const candidates = filterSlash(query)
  const items = toItems(candidates)

  const [highlighted, setHighlighted] = React.useState<string | null>(
    items[0]?.value ?? null
  )

  // 후보 리스트 변경 시 highlighted 재계산
  React.useEffect(() => {
    if (items.length === 0) {
      setHighlighted(null)
      return
    }
    // 현재 highlighted 가 더 이상 candidates 에 없으면 첫 번째로 리셋
    const stillExists = items.some((i) => i.value === highlighted)
    if (!stillExists) {
      setHighlighted(items[0]?.value ?? null)
    }
  // query 변경 시마다 재확인 — items 는 render-phase 파생값이므로 dependency 에서 제외
  }, [query])

  useInput((input, key) => {
    if (key.escape) {
      onClose()
      return
    }
    if (key.tab) {
      if (highlighted) {
        onSelect(highlighted)
      }
      return
    }
    // Enter / 일반 문자 / 화살표 등은 처리하지 않음
    // ink-select-input 이 화살표, Enter 를 내부 처리
    // Enter 는 방어적으로 onSelect 도 호출 (T-02C-05 완화)
    if (key.return && highlighted) {
      onSelect(highlighted)
    }
  })

  if (items.length === 0) {
    return (
      <Box borderStyle='round' borderColor='gray' paddingX={1}>
        <Text dimColor>일치하는 명령이 없습니다</Text>
      </Box>
    )
  }

  return (
    <Box flexDirection='column' borderStyle='round' borderColor='cyan' paddingX={1}>
      <SelectInput
        items={items}
        onHighlight={(item: SelectItem) => setHighlighted(item.value)}
        // Enter 도 onSelect 경로로 연결 (T-02C-05: SelectInput 이 Enter 를 consume 해도 buffer 교체 일관성 유지)
        onSelect={(item: SelectItem) => onSelect(item.value)}
      />
    </Box>
  )
}
