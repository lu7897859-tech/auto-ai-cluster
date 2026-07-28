const fs = require('fs');

// Read remote blog index
let idx = fs.readFileSync('docs/blog/index.html', 'utf8');

// Insert blog #20 entry before the blog-22/23/24 entries
const newEntry = '<li><a href="/auto-ai-cluster/docs/blog/20-cost-effective-ai-inference-hybrid-routing.html">20 \u2014 Cost-Effective AI Inference: Hybrid Routing Between Cloud APIs and Local LLMs</a> <small>(2026-07-28)</small><br><small>Implement a hybrid AI inference routing strategy that balances cost, latency, and quality. Route high-value queries to cloud APIs, handle volume workloads locally on 2C4G.</small></li>\n';

// Insert before the blog-22 line
idx = idx.replace("  <li><a href='../blog-22.html'>", newEntry + "  <li><a href='../blog-22.html'>");
fs.writeFileSync('docs/blog/index.html', idx, 'utf8');
console.log('Added blog #20 to index');

// Update sitemap.xml
let sm = fs.readFileSync('sitemap.xml', 'utf8');
const newUrl = '  <url><loc>https://lu7897859-tech.github.io/auto-ai-cluster/docs/blog/20-cost-effective-ai-inference-hybrid-routing.html</loc><lastmod>2026-07-28</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>\n';
// Insert before the blog-22 line in sitemap
sm = sm.replace('  <url><loc>https://lu7897859-tech.github.io/auto-ai-cluster/blog-22.html', newUrl + '  <url><loc>https://lu7897859-tech.github.io/auto-ai-cluster/blog-22.html');
fs.writeFileSync('sitemap.xml', sm, 'utf8');
console.log('Added blog #20 to sitemap');

// Update feed.xml
let feed = fs.readFileSync('feed.xml', 'utf8');
const newFeedEntry = '\n<entry>\n<title>20 \u2014 Cost-Effective AI Inference: Hybrid Routing Between Cloud APIs and Local LLMs</title>\n<link href="https://lu7897859-tech.github.io/auto-ai-cluster/docs/blog/20-cost-effective-ai-inference-hybrid-routing.html"/>\n<id>https://lu7897859-tech.github.io/auto-ai-cluster/docs/blog/20-cost-effective-ai-inference-hybrid-routing.html</id>\n<updated>2026-07-28T00:00:00Z</updated>\n<summary>Implement a hybrid AI inference routing strategy that balances cost, latency, and quality.</summary>\n</entry>';
feed = feed.replace('<entry>\n<title>19 ', newFeedEntry + '\n<entry>\n<title>19 ');
fs.writeFileSync('feed.xml', feed, 'utf8');
console.log('Added blog #20 to feed');

console.log('=== DONE ===');
