import { render, screen } from '@testing-library/vue';

import InputCard from './InputCard.vue';

test('renders reusable input metadata and assigned display count', () => {
  render(InputCard, {
    props: {
      input: {
        id: 'i-1',
        kind: 'mqtt',
        name: 'Balance Feed',
        assignedDisplayCount: 2,
        autoMode: 'realtime',
        preview: '15568.91',
      },
    },
  });

  expect(screen.getByText('Balance Feed')).toBeInTheDocument();
  expect(screen.getByText('mqtt')).toBeInTheDocument();
  expect(screen.getByText('2 Displays')).toBeInTheDocument();
  expect(screen.getByText('15568.91')).toBeInTheDocument();
});
