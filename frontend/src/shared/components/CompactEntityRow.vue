<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string
    count: string | number
    active?: boolean
    selectLabel?: string
  }>(),
  {
    active: false,
    selectLabel: undefined,
  },
)

defineEmits<{
  select: []
}>()
</script>

<template>
  <article
    class="compact-entity-row"
    :class="{ 'compact-entity-row--active': active }"
    :data-active="active"
    @click="$emit('select')"
  >
    <button
      class="compact-entity-row__select"
      type="button"
      :aria-label="selectLabel ?? title"
      :aria-pressed="active"
    >
      <span class="compact-entity-row__icon" aria-hidden="true">
        <slot name="icon" />
      </span>
      <strong class="compact-entity-row__title" :title="title">
        <slot name="title">{{ title }}</slot>
      </strong>
      <span class="compact-entity-row__count">
        <slot name="count">{{ count }}</slot>
      </span>
      <span class="compact-entity-row__status">
        <slot name="status" />
      </span>
    </button>
    <div class="compact-entity-row__actions" @click.stop>
      <slot name="actions" />
    </div>
  </article>
</template>

<style scoped>
.compact-entity-row {
  display: grid;
  width: 100%;
  height: var(--table-list-row-slot-height);
  min-width: 0;
  grid-template-columns: minmax(0, 1fr) var(--control-height-default);
  align-items: center;
  gap: var(--space-1);
  padding: 0 var(--space-1) 0 var(--space-2);
  overflow: hidden;
  border: 1px solid transparent;
  border-radius: var(--radius-control);
  cursor: pointer;
}

.compact-entity-row + .compact-entity-row {
  margin-top: var(--space-1);
}

.compact-entity-row:hover {
  background: var(--bg-surface-hover);
}

.compact-entity-row--active {
  border-color: var(--border-default);
  background: var(--color-primary-soft);
}

.compact-entity-row__select {
  display: grid;
  width: 100%;
  height: 100%;
  min-width: 0;
  padding: 0;
  border: 0;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: inherit;
  grid-template-columns:
    var(--control-height-compact)
    minmax(0, 1fr)
    max-content
    var(--space-3);
  align-items: center;
  gap: var(--space-1);
  background: transparent;
}

.compact-entity-row__icon {
  display: grid;
  width: var(--control-height-compact);
  height: var(--control-height-compact);
  place-items: center;
  color: var(--text-tertiary);
}

.compact-entity-row--active .compact-entity-row__icon {
  color: var(--text-link);
}

.compact-entity-row__title {
  min-width: 0;
  overflow: hidden;
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-entity-row__count {
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.compact-entity-row__status {
  display: grid;
  width: var(--space-3);
  place-items: center;
}

.compact-entity-row__actions {
  display: grid;
  width: var(--control-height-default);
  height: 100%;
  min-width: 0;
  place-items: center;
}

.compact-entity-row__actions :deep(button) {
  width: var(--control-height-default);
  min-width: var(--control-height-default);
  padding-right: 0;
  padding-left: 0;
}
</style>
