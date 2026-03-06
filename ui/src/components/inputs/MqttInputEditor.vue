<script setup lang="ts">
import { computed } from 'vue';

import { useDisplayActions } from '../../composables/useDisplayActions';
import { useTopicBrowser } from '../../composables/useTopicBrowser';
import { useRuntimeStore } from '../../stores/runtime';
import { useWorkspaceStore } from '../../stores/workspace';
import { splitTopic } from '../../utils/mqtt';
import SaveStatusBadge from '../common/SaveStatusBadge.vue';
import BindingChips from './BindingChips.vue';
import TopicBrowser from '../mqtt/TopicBrowser.vue';

const props = defineProps<{
  inputId: string;
}>();

const workspace = useWorkspaceStore();
const runtime = useRuntimeStore();
const actions = useDisplayActions();

const input = computed(() => workspace.inputById(props.inputId));
const assignedDisplays = computed(() => workspace.assignedDisplays(props.inputId));
const liveValue = computed(() => runtime.inputValues[props.inputId]?.value || '-');

const browser = useTopicBrowser(() => {
  const current = input.value;
  if (!current || current.kind !== 'mqtt') {
    return {
      brokerHost: '',
      brokerPort: 1883,
      topic: '',
      topicSearch: '',
      jsonKey: '',
      timeout: 4,
    };
  }
  return {
    brokerHost: current.brokerHost,
    brokerPort: current.brokerPort,
    topic: current.topic,
    topicSearch: current.topicSearch,
    jsonKey: current.jsonKey,
    timeout: current.timeout,
  };
});

const browserItems = computed(() => browser.items.value);
const browserBreadcrumb = computed(() => browser.breadcrumb.value);

async function sendNow() {
  if (input.value?.kind !== 'mqtt') {
    return;
  }
  await actions.sendMqttInputToDisplays(input.value, assignedDisplays.value);
}

async function fetchNow() {
  if (input.value?.kind !== 'mqtt') {
    return;
  }
  const detail = await actions.fetchMqttInputValue(input.value);
  runtime.setInputValue(input.value.id, {
    value: detail.preview,
    rawPayload: detail.rawPayload,
    topic: detail.topic,
    updatedAtMs: detail.receivedAtMs || Date.now(),
    messageNo: detail.messageNo,
    stale: false,
  });
}

function updateField(field: string, value: string | number) {
  if (!input.value || input.value.kind !== 'mqtt') {
    return;
  }
  workspace.updateInput(input.value.id, { [field]: value } as never);
}

function selectTopic(path: string) {
  if (!input.value || input.value.kind !== 'mqtt') {
    return;
  }
  workspace.updateInput(input.value.id, { topic: path });
}

function jumpToPath(path: string) {
  void browser.navigate(path);
}

function navigateItem(item: { path: string }) {
  void browser.navigate(item.path);
}

function selectItem(item: { path: string }) {
  selectTopic(item.path);
}

const samplePreview = computed(() => browser.detail.value?.previewValue || liveValue.value);
const samplePayload = computed(() => browser.detail.value?.rawPayload || runtime.inputValues[props.inputId]?.rawPayload || '-');
const keyChips = computed(() => browser.detail.value?.jsonKeys || []);
const pathSegments = computed(() => splitTopic(input.value?.kind === 'mqtt' ? input.value.topic : ''));
const editorSaveState = computed(() => workspace.inputSaveState(props.inputId));
const editorSaveLabel = computed(() => workspace.inputSaveLabel(props.inputId));
const editorSaveNote = computed(() => {
  if (editorSaveState.value === 'error') {
    return workspace.saveError || 'Speichern fehlgeschlagen.';
  }
  if (editorSaveState.value === 'dirty') {
    return 'Topic, Broker und Zuordnung bleiben lokal, bis du speicherst.';
  }
  return workspace.saveNote;
});
</script>

<template>
  <section v-if="input && input.kind === 'mqtt'" class="editor-panel">
    <div class="editor-head">
      <div>
        <p class="eyebrow">MQTT Skill</p>
        <h2>{{ input.name }}</h2>
      </div>
      <div class="inline-actions">
        <button type="button" class="ghost-btn" @click="browser.sync()">Topics syncen</button>
        <button type="button" class="ghost-btn" @click="fetchNow">Wert laden</button>
        <button type="button" class="primary-btn" @click="sendNow">An Displays senden</button>
      </div>
    </div>

    <SaveStatusBadge :state="editorSaveState" :label="editorSaveLabel" :note="editorSaveNote">
      <button type="button" class="ghost-btn" :disabled="!workspace.canDiscard" @click="workspace.discardChanges()">Verwerfen</button>
      <button type="button" class="primary-btn" :disabled="!workspace.canSave" @click="workspace.saveNow()">Speichern</button>
    </SaveStatusBadge>

    <div class="field-grid three">
      <div class="field-stack">
        <label>Name</label>
        <input :value="input.name" @input="updateField('name', ($event.target as HTMLInputElement).value)" />
      </div>
      <div class="field-stack">
        <label>Broker-IP</label>
        <input :value="input.brokerHost" @input="updateField('brokerHost', ($event.target as HTMLInputElement).value)" />
      </div>
      <div class="field-stack">
        <label>Port</label>
        <input type="number" min="1" max="65535" :value="input.brokerPort" @input="updateField('brokerPort', Number(($event.target as HTMLInputElement).value))" />
      </div>
    </div>

    <div class="field-grid two">
      <div class="field-stack">
        <label>Sendemodus</label>
        <select
          :value="input.delivery.sendMode"
          @change="workspace.updateInput(input.id, { delivery: { ...input.delivery, sendMode: ($event.target as HTMLSelectElement).value } })"
        >
          <option value="realtime">real time</option>
          <option v-for="sec in 10" :key="sec" :value="String(sec)">{{ sec }}s</option>
          <option value="off">off</option>
        </select>
      </div>
      <div class="field-stack">
        <label>Anzeigezeit</label>
        <select
          :value="input.delivery.displayDuration"
          @change="workspace.updateInput(input.id, { delivery: { ...input.delivery, displayDuration: ($event.target as HTMLSelectElement).value } })"
        >
          <option v-for="sec in 10" :key="sec" :value="String(sec)">{{ sec }}s</option>
          <option value="until-change">bis wertänderung</option>
        </select>
      </div>
    </div>

    <div class="field-grid two">
      <div class="field-stack">
        <label>Topic-Suche</label>
        <input :value="input.topicSearch" placeholder="topic / payload / key" @input="updateField('topicSearch', ($event.target as HTMLInputElement).value)" />
      </div>
      <div class="field-stack">
        <label>Gewähltes Topic</label>
        <input :value="input.topic" placeholder="Topic aus dem Browser wählen" @input="updateField('topic', ($event.target as HTMLInputElement).value)" />
      </div>
    </div>

    <div class="field-grid topic-layout">
      <TopicBrowser
        :items="browserItems"
        :breadcrumb="browserBreadcrumb"
        @navigate="navigateItem"
        @select="selectItem"
        @jump="jumpToPath"
      />

      <section class="topic-detail-card">
        <p class="eyebrow">Topic Detail</p>
        <strong>{{ input.topic || pathSegments.join('/') || '-' }}</strong>
        <div class="preview-panel">
          <span>Letzter Wert</span>
          <strong>{{ samplePreview }}</strong>
        </div>
        <div class="field-stack">
          <label>JSON-Key</label>
          <input :value="input.jsonKey" placeholder="balance" @input="updateField('jsonKey', ($event.target as HTMLInputElement).value)" />
        </div>
        <div class="tag-row">
          <button
            v-for="key in keyChips"
            :key="key"
            type="button"
            class="tag-pill"
            :data-selected="input.jsonKey === key"
            @click="updateField('jsonKey', key)"
          >
            {{ key }}
          </button>
        </div>
        <div class="field-stack">
          <label>Template</label>
          <input
            :value="input.delivery.template"
            placeholder="Balance: {value}"
            @input="workspace.updateInput(input.id, { delivery: { ...input.delivery, template: ($event.target as HTMLInputElement).value } })"
          />
        </div>
        <div class="field-stack">
          <label>Payload-Sample</label>
          <textarea readonly :value="samplePayload" />
        </div>
      </section>
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
