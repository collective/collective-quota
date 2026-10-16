type PredicateArgs = { location?: { pathname?: string } };

// Slot predicate: true unless the current path starts with one of `paths`.
export const notOnRoutes =
  (paths: string[]) =>
  ({ location }: PredicateArgs): boolean =>
    !paths.some((path) => location?.pathname?.startsWith(path));
