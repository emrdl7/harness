---
name: SCSS BEM 코딩 컨벤션
keywords: scss, css, bem, 스타일, 스타일시트, 클래스, 네이밍, sass, 전처리기
---

# SCSS BEM 컨벤션

## 기본 규칙
- 인라인 스타일 사용 금지
- `!important` 사용 금지 (부득이한 경우 주석 필수)
- 들여쓰기 2 spaces
- 따옴표 single quote
- 세미콜론 없음 (dart-sass)

## BEM 네이밍
```scss
// Block
.card { }

// Element
.card__title { }
.card__image { }

// Modifier
.card--featured { }
.card__title--large { }
```

## SCSS 중첩 패턴
```scss
.card {
  &__title { }
  &__image { }
  &--featured { }

  // 상태
  &:hover { }
  &:focus-visible { }

  // 미디어쿼리는 요소 안에
  @media (max-width: 768px) { }
}
```

## 변수/토큰
- 색상, 간격, 폰트는 CSS 변수(`--`) 또는 SCSS 변수(`$`) 사용
- 컴포넌트별 지역 변수는 `$_` 접두사
