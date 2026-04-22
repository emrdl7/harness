---
name: Vue 웹접근성 패턴
keywords: vue, 접근성, aria, wcag, 웹접근성, a11y, 스크린리더, 키보드, 포커스, 슬라이더, swiper, 모달, 탭, 아코디언
---

# Vue 웹접근성 패턴 (WCAG 2.1 AA)

## 기본 원칙
- 이미지에 `alt` 필수 (장식용은 `alt=""`)
- 인터랙티브 요소에 `aria-label` 또는 텍스트 레이블 필수
- 키보드 네비게이션 지원 (`tabindex`, `@keydown`)
- 색상 대비 4.5:1 이상

## Swiper 슬라이더
```vue
<swiper
  role="region"
  aria-label="슬라이드 목록"
  aria-live="polite"
  :a11y="{ enabled: true, prevSlideMessage: '이전 슬라이드', nextSlideMessage: '다음 슬라이드' }"
>
  <swiper-slide v-for="(item, i) in items" :key="i" :aria-label="`${i+1}번째 슬라이드`">
  </swiper-slide>
</swiper>
```

## 모달
```vue
<div role="dialog" aria-modal="true" :aria-labelledby="titleId" @keydown.esc="close">
  <h2 :id="titleId">제목</h2>
  <button @click="close" aria-label="닫기">×</button>
</div>
```
모달 열릴 때 포커스 이동: `nextTick(() => modalRef.value?.focus())`
모달 닫힐 때 트리거 버튼으로 포커스 복귀

## 탭
```vue
<div role="tablist">
  <button
    v-for="(tab, i) in tabs"
    role="tab"
    :aria-selected="activeTab === i"
    :aria-controls="`panel-${i}`"
    :tabindex="activeTab === i ? 0 : -1"
    @keydown.right="activeTab = (i+1) % tabs.length"
    @keydown.left="activeTab = (i-1+tabs.length) % tabs.length"
  >{{ tab.label }}</button>
</div>
<div
  v-for="(tab, i) in tabs"
  role="tabpanel"
  :id="`panel-${i}`"
  :aria-labelledby="`tab-${i}`"
  v-show="activeTab === i"
/>
```

## 아코디언
```vue
<button
  :aria-expanded="isOpen"
  :aria-controls="contentId"
>제목</button>
<div :id="contentId" :hidden="!isOpen">내용</div>
```

## 폼
- `<label :for="id">` 또는 `aria-label`로 모든 입력 필드 레이블 연결
- 오류: `aria-describedby`로 오류 메시지 연결, `aria-invalid="true"`
- 필수: `aria-required="true"`
