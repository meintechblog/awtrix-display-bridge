import { fireEvent, render, screen } from '@testing-library/vue';

import DisplayDrawer from './DisplayDrawer.vue';

test('emits clear and test-send actions for the selected display', async () => {
  const { emitted } = render(DisplayDrawer, {
    props: {
      open: true,
      display: {
        id: 'd-1',
        name: 'Main',
        ip: '192.168.3.126',
        status: 'online',
      },
      assignedInputs: [],
    },
  });

  await fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
  await fireEvent.click(screen.getByRole('button', { name: 'Test senden' }));

  expect(emitted().clear).toHaveLength(1);
  expect(emitted()['test-send']).toHaveLength(1);
});
