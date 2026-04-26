// usePasteCompat — @jrichman/ink 포크에 usePaste 없으므로 bracketed paste 직접 구현
// 표준 Ink 7 usePaste 와 동일한 시그니처로 대체 사용 가능
import {useEffect, useRef} from 'react'
import {useStdin} from 'ink'

export function usePaste(onPaste: (text: string) => void): void {
  const {stdin} = useStdin()
  const bufRef = useRef('')
  const inPasteRef = useRef(false)
  const cbRef = useRef(onPaste)
  cbRef.current = onPaste

  useEffect(() => {
    if (!stdin) return

    const handler = (chunk: Buffer | string) => {
      const str = typeof chunk === 'string' ? chunk : chunk.toString('utf-8')

      if (!inPasteRef.current) {
        const start = str.indexOf('\x1b[200~')
        if (start === -1) return
        inPasteRef.current = true
        const rest = str.slice(start + 6)
        bufRef.current = ''
        // end 가 같은 청크에 있을 수도 있음
        const end = rest.indexOf('\x1b[201~')
        if (end !== -1) {
          cbRef.current(rest.slice(0, end))
          inPasteRef.current = false
          bufRef.current = ''
        } else {
          bufRef.current = rest
        }
      } else {
        const end = str.indexOf('\x1b[201~')
        if (end !== -1) {
          cbRef.current(bufRef.current + str.slice(0, end))
          inPasteRef.current = false
          bufRef.current = ''
        } else {
          bufRef.current += str
        }
      }
    }

    stdin.on('data', handler)
    return () => { stdin.off('data', handler) }
  }, [stdin])
}
