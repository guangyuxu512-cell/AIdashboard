<template>
  <div class="mobile-app-shell">
    <header
      v-if="$slots.header"
      class="mobile-app-shell__header"
      data-testid="mobile-shell-header"
    >
      <slot name="header" />
    </header>

    <main
      class="mobile-app-shell__main"
      data-testid="mobile-shell-main"
      :class="{
        'mobile-app-shell__main--without-header': !$slots.header,
        'mobile-app-shell__main--without-bottom': !$slots.bottom,
      }"
    >
      <slot />
    </main>

    <footer
      v-if="$slots.bottom"
      class="mobile-app-shell__bottom"
      data-testid="mobile-shell-bottom"
    >
      <slot name="bottom" />
    </footer>
  </div>
</template>

<style scoped>
.mobile-app-shell {
  position: relative;
  display: grid;
  width: 100%;
  max-width: var(--layout-content-max-width);
  height: 100dvh;
  min-height: 100dvh;
  margin-inline: auto;
  grid-template-rows: auto minmax(0, 1fr) auto;
  overflow: hidden;
  background: var(--bg-app);
  box-shadow: var(--shadow-shell);
  isolation: isolate;
}

.mobile-app-shell__header {
  position: relative;
  z-index: 2;
  min-width: 0;
  padding-top: var(--safe-area-top);
  background: var(--bg-surface-raised);
}

.mobile-app-shell__main {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.mobile-app-shell__main--without-header {
  padding-top: var(--safe-area-top);
}

.mobile-app-shell__main--without-bottom {
  padding-bottom: var(--safe-area-bottom);
}

.mobile-app-shell__bottom {
  position: relative;
  z-index: 2;
  min-width: 0;
  padding-bottom: var(--safe-area-bottom);
  background: var(--bg-surface-raised);
}

@supports not (height: 100dvh) {
  .mobile-app-shell {
    height: 100vh;
    min-height: 100vh;
  }
}
</style>
