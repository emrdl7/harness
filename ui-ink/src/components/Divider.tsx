// 구분선 컴포넌트 — D-02 active↔input, input↔statusbar 두 자리에서 사용 (RND-04)
import React from 'react'
import {Text, useStdout} from 'ink'

interface DividerProps {
  columns?: number   // 테스트 편의용 override — 미지정 시 stdout.columns
  char?: string      // 기본 '─'
}

export const Divider: React.FC<DividerProps> = ({columns, char = '─'}) => {
  const {stdout} = useStdout()
  const width = Math.max(1, columns ?? stdout?.columns ?? 80)
  return <Text dimColor>{char.repeat(width)}</Text>
}
