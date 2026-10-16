import { human } from './format';

describe('human', () => {
  it.each([
    [0, '0 KB'],
    [1, '1 KB'],
    [1023, '1 KB'],
    [1024, '1.0 KB'],
    [1536, '1.5 KB'],
    [2 * 1024 ** 2, '2.0 MB'],
    [3650722201, '3.4 GB'],
    [5 * 1024 ** 3, '5.0 GB'],
    [2 * 1024 ** 4, '2.0 TB'],
    [3 * 1024 ** 5, '3.0 PB'],
    [2.25 * 1024 ** 2, '2.2 MB'],
    [2.75 * 1024 ** 2, '2.8 MB'],
    [1075, '1.0 KB'],
    [1127, '1.1 KB'],
  ])(
    '%d bytes is %s like plone.base.utils.human_readable_size',
    (size, text) => {
      expect(human(size)).toBe(text);
    },
  );

  it('treats negative sizes as nothing', () => {
    expect(human(-5)).toBe('0 KB');
  });
});
