<script setup lang="ts">
import { computed } from 'vue';

import { useDisplayActions } from '../../composables/useDisplayActions';
import { useWorkspaceStore } from '../../stores/workspace';
import SaveStatusBadge from '../common/SaveStatusBadge.vue';
import BindingChips from './BindingChips.vue';

const props = defineProps<{
  inputId: string;
}>();

const workspace = useWorkspaceStore();
const actions = useDisplayActions();

const input = computed(() => workspace.inputById(props.inputId));
const assignedDisplays = computed(() => workspace.assignedDisplays(props.inputId));
const editorSaveState = computed(() => workspace.inputSaveState(props.inputId));
const editorSaveLabel = computed(() => workspace.inputSaveLabel(props.inputId));
const editorSaveNote = computed(() => {
  if (editorSaveState.value === 'error') {
    return workspace.saveError || 'Speichern fehlgeschlagen.';
  }
  if (editorSaveState.value === 'dirty') {
    return 'Text und Zuordnung bleiben lokal, bis du speicherst.';
  }
  return workspace.saveNote;
});

async function sendNow() {
  if (input.value?.kind !== 'text') {
    return;
  }
  await actions.sendTextInputToDisplays(input.value, assignedDisplays.value);
}
</script>

<template>
  <section v-if="input && input.kind === 'text'" class="editor-panel">
    <div class="editor-head">
      <div>
        <p class="eyebrow">Text Input</p>
        <h2>{{ input.name }}</h2>
      </div>
      <button type="button" class="primary-btn" @click="sendNow">An Displays senden</button>
    </div>

    <SaveStatusBadge :state="editorSaveState" :label="editorSaveLabel" :note="editorSaveNote">
      <button type="button" class="ghost-btn" :disabled="!workspace.canDiscard" @click="workspace.discardChanges()">Verwerfen</button>
      <button type="button" class="primary-btn" :disabled="!workspace.canSave" @click="workspace.saveNow()">Speichern</button>
    </SaveStatusBadge>

    <div class="field-grid two">
      <div class="field-stack">
        <label>Name</label>
        <input :value="input.name" @input="workspace.updateInput(input.id, { name: ($event.target as HTMLInputElement).value })" />
      </div>
      <div class="field-stack">
        <label>Dauer</label>
        <input type="number" min="1" max="120" :value="input.duration" @input="workspace.updateInput(input.id, { duration: Number(($event.target as HTMLInputElement).value) })" />
      </div>
    </div>

    <div class="field-stack">
      <label>Text</label>
      <textarea :value="input.text" @input="workspace.updateInput(input.id, { text: ($event.target as HTMLTextAreaElement).value })" />
    </div>

    <div class="field-stack">
      <label>Ziel-Displays</label>
      <BindingChips
        :displays="workspace.displays"
        :selected-ids="workspace.assignedDisplayIds(input.id)"
        @toggle="workspace.toggleDisplayAssignment(input.id, $event)"
      />
    </div>
  </section>
</template>
