<template>
  <div class="three-pane-workbench">
    <div class="three-pane-workbench__pane three-pane-workbench__pane--left">
      <slot name="left" />
    </div>
    <div class="three-pane-workbench__pane three-pane-workbench__pane--main">
      <slot name="main" />
    </div>
    <div class="three-pane-workbench__pane three-pane-workbench__pane--right">
      <slot name="right" />
    </div>
  </div>
</template>

<style scoped>
.three-pane-workbench {
  display: grid;
  min-width: 0;
  min-height: 0;
  flex: 1;
  gap: var(--layout-card-gap);
  grid-template-columns:
    var(--field-width-md)
    minmax(var(--field-width-md), 1fr)
    var(--field-width-lg);
  overflow: hidden;
}

.three-pane-workbench__pane {
  display: flex;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--bg-surface-solid);
}

.three-pane-workbench__pane--left,
.three-pane-workbench__pane--right {
  background: var(--bg-subtle);
}

.three-pane-workbench__pane--right {
  overflow-y: auto;
  scrollbar-width: none;
}

.three-pane-workbench__pane--right::-webkit-scrollbar {
  display: none;
}

@media (max-width: 1200px) {
  .three-pane-workbench {
    grid-template-columns:
      var(--field-width-md)
      minmax(var(--field-width-md), 1fr)
      var(--field-width-md);
  }
}

@media (max-width: 940px) {
  .three-pane-workbench {
    grid-template-columns: var(--field-width-md) minmax(0, 1fr);
    overflow-y: auto;
    scrollbar-width: none;
  }

  .three-pane-workbench::-webkit-scrollbar {
    display: none;
  }

  .three-pane-workbench__pane--left,
  .three-pane-workbench__pane--main {
    min-height: var(--field-width-xl);
  }

  .three-pane-workbench__pane--right {
    min-height: var(--field-width-lg);
    grid-column: 1 / -1;
  }
}

@media (max-width: 720px) {
  .three-pane-workbench {
    grid-template-columns: minmax(0, 1fr);
  }

  .three-pane-workbench__pane--right {
    grid-column: auto;
  }
}
</style>
