export interface Store<T> {
  get(): T;
  set(next: T): void;
  update(patch: (current: T) => Partial<T>): void;
  subscribe(fn: (next: T) => void): () => void;
  select<U>(selector: (state: T) => U, fn: (next: U) => void): () => void;
}

export function createStore<T extends object>(initial: T): Store<T> {
  let state = initial;
  const subs = new Set<(next: T) => void>();

  const notify = (): void => subs.forEach((s) => s(state));

  return {
    get: () => state,
    set: (next) => {
      state = next;
      notify();
    },
    update: (patch) => {
      state = { ...state, ...patch(state) };
      notify();
    },
    subscribe(fn) {
      subs.add(fn);
      return () => {
        subs.delete(fn);
      };
    },
    select(selector, fn) {
      let prev = selector(state);
      const wrapper = (next: T): void => {
        const v = selector(next);
        if (v !== prev) {
          prev = v;
          fn(v);
        }
      };
      subs.add(wrapper);
      return () => {
        subs.delete(wrapper);
      };
    },
  };
}
