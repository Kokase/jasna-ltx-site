const callbacks = new WeakMap();
let observer;

export function observeImageVisibility(element, onChange) {
  observer ??= new IntersectionObserver((entries) => {
    for (const entry of entries) {
      callbacks.get(entry.target)?.(entry.isIntersecting);
    }
  }, { rootMargin: '300px' });

  callbacks.set(element, onChange);
  observer.observe(element);
  return () => {
    observer.unobserve(element);
    callbacks.delete(element);
  };
}
