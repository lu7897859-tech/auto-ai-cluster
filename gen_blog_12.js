const fs = require('fs');
const path = require('path');

const ROOT = 'C:\\Users\\Administrator\\Documents\\Auto-AI-Cluster-Whole-Project';
const BLOG = path.join(ROOT, 'docs', 'blog');

function mdToHtml(content) {
  let h = content;
  h = h.replace(/^### (.+)/gm, '<h3>$1</h3>');
  h = h.replace(/^## (.+)/gm, '<h2>$1</h2>');
  h = h.replace(/^# (.+)/gm, '<h1>$1</h1>');
  h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  h = h.replace(/```(\w*)\n?/g, '<pre><code>');
  h = h.replace(/```/g, '</code></pre>');
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
  h = h.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
  h = h.replace(/^-\s\[(.)\]\s(.+)/gm, '<li><input type="checkbox" disabled $1="checked"> $2</li>');
  h = h.replace(/^---$/gm, '<hr>');
  h = h.replace(/^\|(.+)\|$/gm, m => {
    const c = m.split('|').filter(x => x.trim());
    if (c.every(x => /^[-:]+$/.test(x.trim()))) return '';
    const tag = m.includes('---') ? 'th' : 'td';
    return '<tr>' + c.map(x => `<${tag}>${x.trim()}</${tag}>`).join('') + '</tr>';
  });
  const lines = h.split('\n');
  let out = '', pre = false, tbl = false;
  for (const line of lines) {
    const t = line.trim();
    if (t.includes('<pre>')) pre = true;
    if (t.includes('</pre>')) { pre = false; out += line + '\n'; continue; }
    if (pre) { out += line + '\n'; continue; }
    if (t.startsWith('<table')) tbl = true;
    if (t.startsWith('</table>')) { tbl = false; out += line + '\n'; continue; }
    if (tbl) { out += line + '\n'; continue; }
    if (!t) { out += '\n'; continue; }
    if (/^<(\/)?(h[1-6]|pre|code|ul|ol|li|p|hr|a|small|strong|table|tr|td|th|blockquote|div|input)/.test(t)) {
      out += line + '\n';
    } else if (t.startsWith('- ') || t.startsWith('* ') || t.match(/^\d+\.\s/)) {
      out += line + '\n';
    } else {
      out += '<p>' + t + '</p>\n';
    }
  }
  return out;
}

// Process blog 12 only
const mdFiles = ['12-telegram-ai-bot-n8n-tutorial.md'];

for (const f of mdFiles) {
  const content = fs.readFileSync(path.join(BLOG, f), 'utf8');
  const titleMatch = content.match(/^# (.+)/m);
  const title = titleMatch ? titleMatch[1].trim() : 'Untitled';
  const dateMatch = content.match(/^\*\*Published:\*\*\s*(\d{4}-\d{2}-\d{2})/m);
  const date = dateMatch ? dateMatch[1] : '2026-07-19';
  const tagMatch = content.match(/^\*\*Tags:\*\*\s*(.+)/m);
  const tags = tagMatch ? tagMatch[1].split(',').map(t => t.trim()) : [];
  const body = mdToHtml(content);

  const tagHtml = tags.map(t => `<span class="tag">${t}</span>`).join('\n  ');
  const desc = 'Build a Telegram AI bot agent on your 2C4G VPS with n8n. Complete tutorial from BotFather setup to production deployment with AI gateway integration.';

  const jsonld = JSON.stringify({
    "@context": "https://schema.org", "@type": "TechArticle",
    "headline": title, "datePublished": date,
    "author": {"@type": "Person", "name": "Auto-AI-Cluster"},
    "description": desc
  });

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${title} | Auto-AI-Cluster Blog</title>
<meta name="description" content="${desc}">
<meta name="robots" content="index,follow">
<link rel="canonical" href="https://lu7897859-tech.github.io/auto-ai-cluster/docs/blog/">
<meta property="og:image" content="https://lu7897859-tech.github.io/auto-ai-cluster/og-image.svg">
<style>
body{max-width:800px;margin:0 auto;padding:20px;font-family:-apple-system,sans-serif;line-height:1.8;color:#c9d1d9;background:#0d1117}
h1{color:#58a6ff;border-bottom:1px solid #30363d;padding-bottom:8px}
h2{color:#79c0ff;margin-top:32px}
h3{color:#d2a8ff;margin-top:24px}
a{color:#58a6ff}
pre{background:#161b22;padding:14px;border-radius:6px;overflow-x:auto;font-size:14px;border:1px solid #30363d}
code{background:#161b22;padding:2px 6px;border-radius:3px;font-size:14px}
pre code{background:none;padding:0}
table{border-collapse:collapse;width:100%;margin:16px 0}
th,td{border:1px solid #30363d;padding:8px 12px;text-align:left}
th{background:#161b22}
small{color:#8b949e}
.tag{display:inline-block;background:#1f2937;color:#58a6ff;padding:2px 10px;border-radius:12px;font-size:13px;margin-right:6px}
nav{margin-bottom:20px;font-size:14px}
nav a{color:#8b949e;text-decoration:none}
nav a:hover{color:#58a6ff}
hr{border:none;border-top:1px solid #30363d}
ul,ol{padding-left:24px}
li{margin:4px 0}
p{margin:14px 0}
</style>
</head>
<body>
<nav><a href="https://lu7897859-tech.github.io/auto-ai-cluster/">Home</a> · <a href="https://lu7897859-tech.github.io/auto-ai-cluster/docs/blog/index.html">Blog</a></nav>

<h1>${title}</h1>
<p><small>Published ${date} · 12 min read</small></p>
${tagHtml ? `<p>${tagHtml}</p>` : ''}

${body}

<hr>
<footer><p><small>Part of <a href="https://github.com/lu7897859-tech/auto-ai-cluster">Auto-AI-Cluster</a>. Published ${date}.</small></p></footer>
<script type="application/ld+json">${jsonld}</script>
</body>
</html>`;

  fs.writeFileSync(path.join(BLOG, '12-telegram-ai-bot-n8n-tutorial.html'), html, 'utf8');
  console.log('✅ Generated HTML for blog #12');
}

// ── Update blog index.html ──
const allMd = fs.readdirSync(BLOG).filter(f => f.endsWith('.md') && !f.startsWith('.') && f !== 'survival-first-architecture.md');

const entries = allMd.map(f => {
  const content = fs.readFileSync(path.join(BLOG, f), 'utf8');
  const titleMatch = content.match(/^# (.+)/m);
  const title = titleMatch ? titleMatch[1].trim() : f.replace('.md','');
  const dateMatch = content.match(/^\*\*Published:\*\*\s*(\d{4}-\d{2}-\d{2})/m);
  const date = dateMatch ? dateMatch[1] : '2026-07-16';
  const descP = content.split('\n\n').find(l => l.length > 30 && !l.startsWith('>') && !l.startsWith('#') && !l.startsWith('*'));
  const desc = descP ? descP.trim().substring(0, 120) : title;
  const num = f.match(/^(\d+)/);
  return { title, date, desc, htmlName: f.replace('.md', '.html'), sortKey: num ? parseInt(num[1]) : 99 };
}).sort((a, b) => b.sortKey - a.sortKey);

const links = entries.map(e =>
  `<li><a href="/auto-ai-cluster/docs/blog/${e.htmlName}">${e.title}</a> <small>(${e.date})</small><br><small>${e.desc}</small></li>`
).join('\n');

fs.writeFileSync(path.join(BLOG, 'index.html'), `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Auto-AI-Cluster Blog</title>
<meta name="description" content="Technical blog about autonomous AI clusters, survival-first architecture, self-hosted n8n on 2C4G.">
<meta name="robots" content="index,follow">
<link rel="canonical" href="https://lu7897859-tech.github.io/auto-ai-cluster/docs/blog/index.html">
<meta property="og:image" content="https://lu7897859-tech.github.io/auto-ai-cluster/og-image.svg">
<style>body{max-width:800px;margin:0 auto;padding:20px;font-family:-apple-system,sans-serif;line-height:1.6;color:#c9d1d9;background:#0d1117}h1{color:#58a6ff}a{color:#58a6ff}li{margin:16px 0}small{color:#8b949e}</style>
</head>
<body>
<nav><a href="https://lu7897859-tech.github.io/auto-ai-cluster/">Home</a></nav>
<h1>Auto-AI-Cluster Blog</h1>
<p>Technical articles about survival-first architecture, self-hosted AI agent clusters, n8n deployments, and edge computing.</p>
<ul>
${links}
</ul>
<hr>
<footer><p>Part of <a href="https://github.com/lu7897859-tech/auto-ai-cluster">Auto-AI-Cluster</a></p></footer>
</body>
</html>`, 'utf8');
console.log(`✅ blog/index.html (${entries.length} entries)`);

// ── Update sitemap ──
const today = '2026-07-19';
const allUrls = [
  ['https://lu7897859-tech.github.io/auto-ai-cluster/', today],
  ['https://lu7897859-tech.github.io/auto-ai-cluster/white-paper.html', '2026-07-16'],
  ['https://lu7897859-tech.github.io/auto-ai-cluster/docs/blog/index.html', today],
];
for (const e of entries) {
  allUrls.push([`https://lu7897859-tech.github.io/auto-ai-cluster/docs/blog/${e.htmlName}`, e.date]);
}

let sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n';
for (const [loc, mod] of allUrls) {
  sitemap += `  <url><loc>${loc}</loc><lastmod>${mod}</lastmod></url>\n`;
}
sitemap += '</urlset>';
fs.writeFileSync(path.join(ROOT, 'sitemap.xml'), sitemap, 'utf8');
console.log(`✅ sitemap.xml (${allUrls.length} URLs)`);

// ── Update feed.xml ──
let feed = `<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>Auto-AI-Cluster Blog</title>
<subtitle>Self-hosted autonomous AI cluster frameworks and tutorials</subtitle>
<link href="https://lu7897859-tech.github.io/auto-ai-cluster/docs/blog/index.html"/>
<updated>${today}T00:00:00Z</updated>
<author><name>Auto-AI-Cluster Team</name></author>
<id>https://lu7897859-tech.github.io/auto-ai-cluster/feed.xml</id>`;

for (const e of entries) {
  feed += `
<entry>
<title>${e.title.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</title>
<link href="https://lu7897859-tech.github.io/auto-ai-cluster/docs/blog/${e.htmlName}"/>
<id>https://lu7897859-tech.github.io/auto-ai-cluster/docs/blog/${e.htmlName}</id>
<updated>${e.date}T00:00:00Z</updated>
<summary>${e.desc.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</summary>
</entry>`;
}
feed += '\n</feed>';
fs.writeFileSync(path.join(ROOT, 'feed.xml'), feed, 'utf8');
console.log('✅ feed.xml');

console.log('\n=== ALL DONE ===');
