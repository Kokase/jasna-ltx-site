export function createSyncAudit(document) {
  let missingCover = 0;
  let missingLinks = 0;
  let missingBoth = 0;
  const records = [];
  for (const item of document.items) {
    const missing = [];
    if (!item.cover?.trim()) {
      missingCover++;
      missing.push('cover');
    }
    if (!(item.links ?? []).some(link => link.trim()) && !item.link?.trim()) {
      missingLinks++;
      missing.push('links');
    }
    if (missing.length === 2) missingBoth++;
    if (missing.length) records.push({ code: item.code, missing });
  }
  return {
    updated_at: document.updated_at,
    total: document.items.length,
    missing_cover: missingCover,
    missing_links: missingLinks,
    missing_both: missingBoth,
    complete: document.items.length - records.length,
    records,
  };
}
