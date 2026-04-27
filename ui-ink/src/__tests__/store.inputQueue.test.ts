// AR-04: input queue 단위 테스트
// - enqueue / dequeue FIFO
// - 빈 텍스트 무시
// - clear 동작
// - kind 보존
import {describe, it, expect, beforeEach} from 'vitest'
import {useInputQueueStore} from '../store/inputQueue.js'

describe('AR-04 — useInputQueueStore', () => {
  beforeEach(() => {
    useInputQueueStore.setState({queue: []})
  })

  it('Test 1: enqueue 후 queue.length 증가', () => {
    const {enqueue} = useInputQueueStore.getState()
    enqueue('first')
    enqueue('second')
    expect(useInputQueueStore.getState().queue).toHaveLength(2)
  })

  it('Test 2: dequeue FIFO — 먼저 enqueue 한 게 먼저 나옴', () => {
    const {enqueue, dequeue} = useInputQueueStore.getState()
    enqueue('first')
    enqueue('second')
    enqueue('third')
    const a = dequeue()
    const b = dequeue()
    expect(a?.text).toBe('first')
    expect(b?.text).toBe('second')
    expect(useInputQueueStore.getState().queue).toHaveLength(1)
    expect(useInputQueueStore.getState().queue[0]?.text).toBe('third')
  })

  it('Test 3: dequeue 빈 큐 → null', () => {
    const next = useInputQueueStore.getState().dequeue()
    expect(next).toBeNull()
  })

  it('Test 4: enqueue 빈 텍스트/공백만 → 무시', () => {
    const {enqueue} = useInputQueueStore.getState()
    enqueue('')
    enqueue('   ')
    enqueue('\n\n')
    expect(useInputQueueStore.getState().queue).toHaveLength(0)
  })

  it('Test 5: enqueue trim — leading/trailing whitespace 제거', () => {
    useInputQueueStore.getState().enqueue('  hello  ')
    expect(useInputQueueStore.getState().queue[0]?.text).toBe('hello')
  })

  it('Test 6: kind 기본값 steer, 명시 시 followUp 보존', () => {
    const {enqueue} = useInputQueueStore.getState()
    enqueue('a')
    enqueue('b', 'followUp')
    const items = useInputQueueStore.getState().queue
    expect(items[0]?.kind).toBe('steer')
    expect(items[1]?.kind).toBe('followUp')
  })

  it('Test 7: clear() → queue 빈 상태', () => {
    const {enqueue, clear} = useInputQueueStore.getState()
    enqueue('a')
    enqueue('b')
    clear()
    expect(useInputQueueStore.getState().queue).toHaveLength(0)
  })

  it('Test 8: id 와 enqueuedAt 자동 부여 + 중복 없음', () => {
    const {enqueue} = useInputQueueStore.getState()
    enqueue('a')
    enqueue('b')
    enqueue('c')
    const items = useInputQueueStore.getState().queue
    const ids = items.map((q) => q.id)
    expect(new Set(ids).size).toBe(3)
    items.forEach((q) => {
      expect(typeof q.id).toBe('string')
      expect(typeof q.enqueuedAt).toBe('number')
    })
  })
})
