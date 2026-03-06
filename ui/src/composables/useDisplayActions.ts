import { clearDisplayContent, fetchTopicValue, sendNotification } from '../api/client';
import { useRuntimeStore } from '../stores/runtime';
import { extractJsonKeys, extractValueFromPayload, formatTemplate, displayModeSeconds } from '../utils/mqtt';
import type { DisplayConfig, MqttInputConfig, TextInputConfig } from '../types/domain';

export function useDisplayActions() {
  const runtime = useRuntimeStore();

  async function refreshDisplay(display: DisplayConfig) {
    await runtime.refreshDisplayStates([display]);
  }

  async function clearDisplay(display: DisplayConfig) {
    await clearDisplayContent(display.ip);
    await refreshDisplay(display);
  }

  async function sendText(display: DisplayConfig, text: string, displayMode: string | number) {
    const seconds = displayModeSeconds(String(displayMode));
    if (seconds === null) {
      await sendNotification(display.ip, {
        text,
        textCase: 2,
        center: true,
        stack: false,
        wakeup: true,
        hold: true,
      });
    } else {
      await sendNotification(display.ip, {
        text,
        duration: seconds,
        textCase: 2,
        center: true,
        stack: false,
        wakeup: true,
      });
    }
    await refreshDisplay(display);
  }

  async function sendTextInputToDisplays(input: TextInputConfig, displays: DisplayConfig[]) {
    await Promise.all(displays.map((display) => sendText(display, input.text, input.delivery.displayDuration)));
  }

  async function fetchMqttInputValue(input: MqttInputConfig) {
    const result = await fetchTopicValue(input.brokerHost, input.brokerPort, input.topic, input.timeout);
    const preview = extractValueFromPayload(result.payload, input.jsonKey);
    return {
      topic: input.topic,
      rawPayload: result.payload,
      preview,
      jsonKeys: extractJsonKeys(result.payload),
      messageNo: Number(result.message_no || 0),
      receivedAtMs: Number(result.received_at_ms || 0),
    };
  }

  async function sendMqttInputToDisplays(input: MqttInputConfig, displays: DisplayConfig[]) {
    const detail = await fetchMqttInputValue(input);
    runtime.setInputValue(input.id, {
      value: detail.preview,
      rawPayload: detail.rawPayload,
      topic: detail.topic,
      updatedAtMs: detail.receivedAtMs || Date.now(),
      messageNo: detail.messageNo,
      stale: false,
    });
    const text = formatTemplate(input.delivery.template, detail.preview);
    await Promise.all(displays.map((display) => sendText(display, text, input.delivery.displayDuration)));
    return detail;
  }

  async function sendQuickTest(display: DisplayConfig) {
    await sendText(display, 'Test', 3);
  }

  return {
    refreshDisplay,
    clearDisplay,
    sendText,
    sendTextInputToDisplays,
    fetchMqttInputValue,
    sendMqttInputToDisplays,
    sendQuickTest,
  };
}
