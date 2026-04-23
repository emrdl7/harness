// ESLint flat config — Ink 금지 패턴 강제 (FND-10)
import js from '@eslint/js'
import tsParser from '@typescript-eslint/parser'

export default [
  {
    // JS 기본 권장 규칙 — TypeScript 가 커버하는 항목은 비활성화
    ...js.configs.recommended,
    rules: {
      ...js.configs.recommended.rules,
      'no-undef': 'off',        // tsc --noEmit 이 처리
      'no-unused-vars': 'off',  // tsc --noEmit 이 처리
    }
  },
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 2022,
        sourceType: 'module',
        ecmaFeatures: {jsx: true}
      }
    },
    rules: {
      // Ink 이중 렌더 붕괴 방지 (CLAUDE.md 절대 금지)
      'no-restricted-syntax': [
        'error',
        {
          selector: "CallExpression[callee.type='MemberExpression'][callee.object.type='MemberExpression'][callee.object.object.name='process'][callee.object.property.name='stdout'][callee.property.name='write']",
          message: 'process.stdout.write 금지 — Ink 이중 렌더 붕괴. Ink <Text> 컴포넌트 사용'
        },
        {
          selector: "CallExpression[callee.type='MemberExpression'][callee.object.name='console'][callee.property.name='log']",
          message: 'console.log 금지 — Ink 이중 렌더 붕괴. Ink <Text> 컴포넌트 사용'
        },
        {
          selector: "CallExpression[callee.type='MemberExpression'][callee.object.name='console'][callee.property.name='error']",
          message: 'console.error 금지 — Ink 이중 렌더 붕괴. Ink <Text> 컴포넌트 사용'
        },
        {
          selector: "CallExpression[callee.type='MemberExpression'][callee.object.name='console'][callee.property.name='warn']",
          message: 'console.warn 금지 — Ink 이중 렌더 붕괴. Ink <Text> 컴포넌트 사용'
        },
        {
          // child_process.spawn 금지 — Ink 화면 박살 (bun#27766)
          selector: "CallExpression[callee.type='MemberExpression'][callee.object.name='child_process'][callee.property.name='spawn']",
          message: 'child_process.spawn 금지 — Ink 화면 붕괴. 서버에서만 사용'
        },
        {
          // <div> JSX 금지 — Ink 에는 DOM 태그 없음
          selector: "JSXOpeningElement[name.name='div']",
          message: '<div> 금지 — Ink 에는 DOM 태그 없음. <Box> 사용'
        },
        {
          // <span> JSX 금지
          selector: "JSXOpeningElement[name.name='span']",
          message: '<span> 금지 — Ink 에는 DOM 태그 없음. <Text> 사용'
        }
      ]
    }
  }
]
