<script setup lang="ts">
import { computed, ref } from 'vue';

import InputCard from '../components/inputs/InputCard.vue';
import MqttInputEditor from '../components/inputs/MqttInputEditor.vue';
import TextInputEditor from '../components/inputs/TextInputEditor.vue';
import { useRuntimeStore } from '../stores/runtime';
import { useWorkspaceStore } from '../stores/workspace';

const workspace = useWorkspaceStore();
const runtime = useRuntimeStore();

const selectedInputId = ref<string | null>(null);

const cards = computed(() => workspace.inputs.map((input) => ({
  id: input.id,
  kind: input.kind,
  name: input.name,
  assignedDisplayCount: workspace.assignedDisplayIds(input.id).length,
  sendMode: input.delivery?.sendMode || 'off',
  preview: runtime.inputValues[input.id]?.value || '-',
})));

const selectedInput = computed(() => selectedInputId.value ? workspace.inputById(selectedInputId.value) : null);

function addTextInput() {
  selectedInputId.value = workspace.addInput('text');
}

function addMqttInput() {
  selectedInputId.value = workspace.addInput('mqtt');
}
</script>

<template>
  <section class="page-grid inputs-layout">
    <div class="section-head">
      <div>
        <p class="eyebrow">Skills</p>
        <h2>Skill-Bibliothek</h2>
      </div>
      <div class="inline-actions">
        <button type="button" class="ghost-btn" @click="addTextInput">+ Text Skill</button>
        <button type="button" class="primary-btn" @click="addMqttInput">+ MQTT Skill</button>
      </div>
    </div>

    <div class="card-grid compact">
      <InputCard
        v-for="input in cards"
        :key="input.id"
        :input="input"
        @open="selectedInputId = input.id"
        @delete="workspace.removeInput(input.id)"
      />
    </div>

    <TextInputEditor v-if="selectedInput?.kind === 'text'" :input-id="selectedInput.id" />
    <MqttInputEditor v-else-if="selectedInput?.kind === 'mqtt'" :input-id="selectedInput.id" />
    <section v-else class="editor-panel placeholder-panel">
      <p class="eyebrow">Editor</p>
      <h2>Skill auswählen</h2>
      <p>Öffne einen Skill aus der Bibliothek oder lege einen neuen an.</p>
    </section>
  </section>
</template>
