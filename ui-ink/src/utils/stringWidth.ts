// CJK full-width 문자 판별 + 문자열 표시 폭 계산
// 터미널에서 한글/한자/일본어 등은 2칸, ASCII는 1칸

function isFullWidth(code: number): boolean {
  return (
    (code >= 0x1100 && code <= 0x115f) ||   // Hangul Jamo
    (code >= 0x2e80 && code <= 0x303e) ||   // CJK Radicals / Kangxi
    (code >= 0x3040 && code <= 0x33bf) ||   // Hiragana, Katakana, CJK symbols
    (code >= 0x3400 && code <= 0x4dbf) ||   // CJK Ext A
    (code >= 0x4e00 && code <= 0x9fff) ||   // CJK Unified Ideographs
    (code >= 0xac00 && code <= 0xd7af) ||   // Hangul Syllables
    (code >= 0xf900 && code <= 0xfaff) ||   // CJK Compat Ideographs
    (code >= 0xfe10 && code <= 0xfe6f) ||   // CJK Compat Forms
    (code >= 0xff01 && code <= 0xff60) ||   // Fullwidth Forms
    (code >= 0xffe0 && code <= 0xffe6) ||   // Fullwidth Signs
    (code >= 0x20000 && code <= 0x2fa1f)    // CJK Ext B-F, Compat Supplement
  )
}

/** 문자열의 터미널 표시 폭 (CJK = 2칸, 일반 = 1칸) */
export function stringWidth(str: string): number {
  let width = 0
  for (const ch of str) {
    const code = ch.codePointAt(0) ?? 0
    width += isFullWidth(code) ? 2 : 1
  }
  return width
}
