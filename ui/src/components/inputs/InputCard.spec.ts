import { render, screen } from '@testing-library/vue';

import InputCard from './InputCard.vue';

test('renders reusable skill metadata and assigned display count', () => {
  render(InputCard, {
    props: {
      input: {
        id: 'i-1',
        kind: 'mqtt',
        name: 'Balance Feed',
        assignedDisplayCount: 2,
        sendMode: 'realtime',
        preview: '15568.91',
      },
    },
  });

  expect(screen.getByText('Balance Feed')).toBeInTheDocument();
  expect(screen.getByText('MQTT Skill')).toBeInTheDocument();
  expect(screen.getByText('2 Displays')).toBeInTheDocument();
  expect(screen.getByText('15568.91')).toBeInTheDocument();
});
