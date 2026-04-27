import {useState, useEffect} from 'react'
import {useStdout} from 'ink'

export function useTerminalColumns(): number {
  const {stdout} = useStdout()
  const [columns, setColumns] = useState(stdout?.columns || 80)

  useEffect(() => {
    if (!stdout) return
    
    let timeout: NodeJS.Timeout
    const onResize = () => {
      clearTimeout(timeout)
      timeout = setTimeout(() => {
        setColumns(stdout.columns || 80)
      }, 100)
    }

    stdout.on('resize', onResize)
    return () => {
      stdout.off('resize', onResize)
      clearTimeout(timeout)
    }
  }, [stdout])

  return columns
}
