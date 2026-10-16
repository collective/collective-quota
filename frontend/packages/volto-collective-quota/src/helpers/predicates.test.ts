import { notOnRoutes } from './predicates';

describe('notOnRoutes', () => {
  const predicate = notOnRoutes([
    '/quota-usage',
    '/controlpanel/collective-quota',
  ]);

  it('is false on the listed routes and below them', () => {
    expect(predicate({ location: { pathname: '/quota-usage' } })).toBe(false);
    expect(
      predicate({ location: { pathname: '/controlpanel/collective-quota' } }),
    ).toBe(false);
  });

  it('is true elsewhere', () => {
    expect(predicate({ location: { pathname: '/' } })).toBe(true);
    expect(predicate({ location: { pathname: '/news/quota-usage' } })).toBe(
      true,
    );
    expect(predicate({ location: { pathname: '/controlpanel' } })).toBe(true);
  });

  it('is true without a location', () => {
    expect(predicate({})).toBe(true);
  });
});
