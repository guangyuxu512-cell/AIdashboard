<template>
  <div class="table-toolbar">
    <div class="table-toolbar__leading">
      <slot />
    </div>
    <div class="table-toolbar__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.table-toolbar,
.table-toolbar__leading,
.table-toolbar__actions {
  display: flex;
  align-items: center;
}

.table-toolbar {
  min-height: var(--control-height-default);
  justify-content: space-between;
  gap: var(--space-4);
}

.table-toolbar__leading,
.table-toolbar__actions {
  gap: var(--space-3);
}
</style>
