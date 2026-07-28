const fs = require('fs');
const path = require('path');
const BLOG = path.join(__dirname, 'docs', 'blog');
const ROOT = __dirname;

const allMd = fs.readdirSync(BLOG).filter(f => f.endsWith('.html') && !f.startsWith('.') && !f.endsWith('index.html'));
const entries = [];
for (const f of allMd) {
  const c = fs.readFileSync(path.join(BLOG, f), 'utf8');
  const t = c.match(/<title>([^<]+)<\/title>/);
  const title = t ? t[1].split(' — ').pop().replace(' | Auto-AI-Cluster Blog', '') : f;
  const d = c.match(/Published (\d{4}-\d{2}-\d{2})/);
  const date = d ? d[1] : '2026-07-16';
  const descM = c.match(/meta name="description" content="([^"]+)"/);
  const desc = descM ? descM[1].substring(0, 120) : title;
  const num = f.match(/^(\d+)/);
  entries.push({ title, date, desc, htmlName: f, sortKey: num ? parseInt(num[1]) : 99 });
}
entries.sort((a, b) => b.sortKey - a.sortKey);

const links = entries.map(function(e) {
  return '<li><a href="/auto-ai-cluster/docs/blog/' + e.htmlName + '">' + e.title + '</a> <small>(' + e.date + ')</small><br><small>' + e.desc + '</small></li>';
}).join('\n');

const indexHtml = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>Auto-AI-Cluster Blog</title>\n<meta name="description" content="Technical blog about autonomous AI clusters, survival-first architecture, self-hosted n8n on 2C4G.">\n<meta name="robots" content="index,follow">\n<link rel="canonical" href="https://lu7897859-tech.github.io/auto-ai-cluster/docs/blog/index.html">\n<meta property="og:image" content="https://lu7897859-tech.github.io/auto-ai-cluster/og-image.svg">\n<meta property="og:title" content="Auto-AI-Cluster Blog"><meta property="og:description" content="Technical blog about autonomous AI clusters, survival-first architecture, self-hosted n8n on 2C4G."><meta property="og:type" content="website"><meta property="og:url" content="https://lu7897859-tech.github.io/auto-ai-cluster/docs/blog/index.html">\n<style>body{max-width:800px;margin:0 auto;padding:20px;font-family:-apple-system,sans-serif;line-height:1.6;color:#c9d1d9;background:#0d1117}h1{color:#58a6ff}a{color:#58a6ff}li{margin:16px 0}small{color:#8b949e}</style>\n</head>\n<body>\n<nav><a href="https://lu7897859-tech.github.io/auto-ai-cluster/">Home</a></nav>\n<h1>Auto-AI-Cluster Blog</h1>\n<p>Technical articles about survival-first architecture, self-hosted AI agent clusters, n8n deployments, and edge computing.</p>\n<ul>\n' + links + '\n</ul>\n<hr>\n<footer><p>Part of <a href="https://github.com/lu7897859-tech/auto-ai-cluster">Auto-AI-Cluster</a></p></footer>\n</body>\n</html>';

fs.writeFileSync(path.join(BLOG, 'index.html'), indexHtml, 'utf8');
console.log('blog/index.html updated with ' + entries.length + ' entries');

// Update sitemap.xml
const today = '2026-07-28';
const allUrls = [
  ['https://lu7897859-tech.github.io/auto-ai-cluster/', today],
  ['https://lu7897859-tech.github.io/auto-ai-cluster/white-paper.html', '2026-07-20'],
  ['https://lu7897859-tech.github.io/auto-ai-cluster/docs/blog/index.html', today],
  ['https://lu7897859-tech.github.io/auto-ai-cluster/payment/checkout.html', '2026-07-20'],
  ['https://lu7897859-tech.github.io/auto-ai-cluster/payment/trial.html', '2026-07-20'],
];
for (const e of entries) {
  allUrls.push(['https://lu7897859-tech.github.io/auto-ai-cluster/docs/blog/' + e.htmlName, e.date]);
}
allUrls.push(['https://lu7897859-tech.github.io/auto-ai-cluster/test-signal.html', '2026-07-21']);

let sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n';
for (const pair of allUrls) {
  sitemap += '  <url><loc>' + pair[0] + '</loc><lastmod>' + pair[1] + '</lastmod></url>\n';
}
sitemap += '</urlset>';
fs.writeFileSync(path.join(ROOT, 'sitemap.xml'), sitemap, 'utf8');
console.log('sitemap.xml updated with ' + allUrls.length + ' URLs');

// Update feed.xml
let feed = '<?xml version="1.0" encoding="UTF-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">\n<title>Auto-AI-Cluster Blog</title>\n<subtitle>Self-hosted autonomous AI cluster frameworks and tutorials</subtitle>\n<link href="https://lu7897859-tech.github.io/auto-ai-cluster/docs/blog/index.html"/>\n<updated>' + today + 'T00:00:00Z</updated>\n<author><name>Auto-AI-Cluster Team</name></author>\n<id>https://lu7897859-tech.github.io/auto-ai-cluster/feed.xml</id>';
for (const e of entries) {
  const safeTitle = e.title.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  const safeDesc = e.desc.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  feed += '\n<entry>\n<title>' + safeTitle + '</title>\n<link href="https://lu7897859-tech.github.io/auto-ai-cluster/docs/blog/' + e.htmlName + '"/>\n<id>https://lu7897859-tech.github.io/auto-ai-cluster/docs/blog/' + e.htmlName + '</id>\n<updated>' + e.date + 'T00:00:00Z</updated>\n<summary>' + safeDesc + '</summary>\n</entry>';
}
feed += '\n</feed>';
fs.writeFileSync(path.join(ROOT, 'feed.xml'), feed, 'utf8');
console.log('feed.xml updated');

console.log('=== ALL DONE ===');
