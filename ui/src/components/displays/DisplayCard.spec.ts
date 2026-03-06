import { render, screen } from '@testing-library/vue';

import DisplayCard from './DisplayCard.vue';

test('shows display identity, status, preview, and quick actions', () => {
  render(DisplayCard, {
    props: {
      display: {
        id: 'd-1',
        name: 'Main Display',
        ip: '192.168.3.126',
        status: 'online',
        previewUrl: '/live.html?ip=192.168.3.126',
        activeContent: 'Balance: 15568.91',
        batteryLevel: 47,
        externalPowerHint: false,
        assignedInputs: [
          { id: 'i-1', name: 'Balance Feed', kind: 'mqtt' },
        ],
      },
    },
  });

  expect(screen.getByText('Main Display')).toBeInTheDocument();
  expect(screen.getByText('192.168.3.126')).toBeInTheDocument();
  expect(screen.getByText('online')).toBeInTheDocument();
  expect(screen.getByText('Akku 47%')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Clear' })).toBeInTheDocument();
  expect(screen.getByTitle('Display preview')).toBeInTheDocument();
});
