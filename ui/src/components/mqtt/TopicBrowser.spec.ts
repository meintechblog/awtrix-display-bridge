import { fireEvent, render, screen } from '@testing-library/vue';

import TopicBrowser from './TopicBrowser.vue';

test('drills down one level at a time and emits a selected leaf topic', async () => {
  const { emitted } = render(TopicBrowser, {
    props: {
      items: [
        { segment: 'trading-deluxxe', kind: 'branch', path: 'trading-deluxxe' },
        { segment: 'other', kind: 'branch', path: 'other' },
      ],
      breadcrumb: [],
    },
  });

  await fireEvent.click(screen.getByText('trading-deluxxe'));

  expect(emitted().navigate).toHaveLength(1);
});
