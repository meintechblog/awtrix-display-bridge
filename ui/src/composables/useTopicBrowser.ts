import { computed, ref, watch } from 'vue';

import { browseTopics, fetchTopicValue, syncTopics } from '../api/client';
import type { TopicBrowserItem, TopicDetail } from '../types/domain';
import { extractJsonKeys, extractValueFromPayload, splitTopic } from '../utils/mqtt';

type TopicSource = {
  brokerHost: string;
  brokerPort: number;
  topic: string;
  topicSearch: string;
  jsonKey: string;
  timeout: number;
};

export function useTopicBrowser(source: () => TopicSource) {
  const items = ref<TopicBrowserItem[]>([]);
  const currentPrefix = ref('');
  const loading = ref(false);
  const syncing = ref(false);
  const error = ref('');
  const detail = ref<TopicDetail | null>(null);

  const breadcrumb = computed(() => {
    const segments = splitTopic(currentPrefix.value);
    return segments.map((segment, index) => ({
      label: segment,
      path: segments.slice(0, index + 1).join('/'),
    }));
  });

  async function load(prefix = currentPrefix.value) {
    const current = source();
    if (!current.brokerHost) {
      items.value = [];
      return;
    }
    loading.value = true;
    error.value = '';
    try {
      const result = await browseTopics(current.brokerHost, current.brokerPort, prefix, current.topicSearch || '');
      currentPrefix.value = prefix;
      items.value = result.items;
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Topic-Browser konnte nicht geladen werden.';
    } finally {
      loading.value = false;
    }
  }

  async function loadDetail(topic: string) {
    const current = source();
    if (!current.brokerHost || !topic) {
      detail.value = null;
      return;
    }
    try {
      const result = await fetchTopicValue(current.brokerHost, current.brokerPort, topic, Math.min(current.timeout || 4, 4));
      detail.value = {
        topic,
        rawPayload: result.payload,
        jsonKeys: extractJsonKeys(result.payload),
        previewValue: extractValueFromPayload(result.payload, current.jsonKey),
      };
    } catch (err) {
      detail.value = {
        topic,
        rawPayload: '',
        jsonKeys: [],
        previewValue: err instanceof Error ? err.message : 'Topic-Detail nicht verfügbar.',
      };
    }
  }

  async function navigate(path: string) {
    await load(path);
  }

  async function sync() {
    const current = source();
    if (!current.brokerHost) {
      return;
    }
    syncing.value = true;
    try {
      await syncTopics(current.brokerHost, current.brokerPort, Math.max(10, Math.min(current.timeout || 4, 20)));
      await load(currentPrefix.value);
    } finally {
      syncing.value = false;
    }
  }

  watch(
    () => `${source().brokerHost}:${source().brokerPort}:${source().topicSearch}`,
    () => {
      void load(currentPrefix.value);
    },
    { immediate: true },
  );

  watch(
    () => source().topic,
    (topic) => {
      const segments = splitTopic(topic);
      currentPrefix.value = segments.slice(0, -1).join('/');
      if (topic) {
        void loadDetail(topic);
      } else {
        detail.value = null;
      }
    },
    { immediate: true },
  );

  watch(
    () => source().jsonKey,
    () => {
      if (detail.value?.topic) {
        void loadDetail(detail.value.topic);
      }
    },
  );

  return {
    items,
    currentPrefix,
    breadcrumb,
    loading,
    syncing,
    error,
    detail,
    load,
    loadDetail,
    navigate,
    sync,
  };
}
