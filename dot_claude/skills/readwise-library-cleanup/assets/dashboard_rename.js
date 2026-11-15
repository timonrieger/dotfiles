// Run on https://readwise.io/library via javascript_tool, only after the user has
// approved using the dashboard API in this session.
// Edit RENAMES: [field, match, new value]. field is 'author' or 'title';
// match is an exact string or a RegExp tested against the current value.
// Only books with highlights are touched. Prints one line per book, then leftovers.
const RENAMES = [
  ['author', /ungeskriptet/, 'Ben Berndt'],
  // ['author', 'de Montaigne, Michel', 'Michel de Montaigne'],
  // ['title', 'Tim Ferris Show', 'The Tim Ferriss Show'],
];
const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1];
const books = async () => {
  const r = await fetch('/api/books/?category=all', { credentials: 'include' }).then(r => r.json());
  return (Array.isArray(r) ? r : (r.results || Object.values(r)[0])).filter(b => b.num_highlights > 0);
};
const match = (value, pat) => (pat instanceof RegExp ? pat.test(value || '') : value === pat);
const out = [];
for (const b of await books()) {
  for (const [field, pat, value] of RENAMES) {
    if (!match(b[field], pat)) continue;
    const r = await fetch(`/api/v2/books/${b.id}/`, {
      method: 'PATCH',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': csrf,
      },
      body: JSON.stringify({ [`${field}_override`]: value }),
    });
    const after = await fetch(`/api/v2/books/${b.id}/`, { credentials: 'include' }).then(r => r.json());
    out.push(`${r.status} ${b.id} ${field}: ${b[field]} -> ${after[field]}`);
  }
}
const left = (await books()).filter(b => RENAMES.some(([f, pat]) => match(b[f], pat)));
out.join('\n') + `\nstill matching old values: ${left.length}`;
