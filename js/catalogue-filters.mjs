export function hasLinks(item) {
  return Boolean(item.link?.trim() || (item.links ?? []).some(link => link.trim()));
}

export function matchesQuickFilters(item, { linked = false, sub = false } = {}) {
  return (!linked || hasLinks(item)) && (!sub || Boolean(item.subtitle?.trim()));
}
