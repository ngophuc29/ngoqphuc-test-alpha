import os
import re
import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
import markdownify

import config

logger = logging.getLogger(__name__)

def slugify(text):
    """
    Convert a string into a URL-friendly slug.
    """
    text = text.lower()
    # Replace non-alphanumeric characters with hyphens
    text = re.sub(r'[^a-z0-9]+', '-', text)
    # Strip leading/trailing hyphens
    return text.strip('-')

def clean_html_links(html_content, base_url):
    """
    Parse HTML and convert relative links (href and src) to absolute URLs.
    """
    if not html_content:
        return ""
        
    soup = BeautifulSoup(html_content, "html.parser")
    parsed_base = urlparse(base_url)
    domain_base = f"{parsed_base.scheme}://{parsed_base.netloc}"
    
    # Resolve relative hrefs in anchor tags
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/"):
            a["href"] = urljoin(domain_base, href)
            
    # Resolve relative srcs in image tags
    for img in soup.find_all("img", src=True):
        src = img["src"]
        if src.startswith("/"):
            img["src"] = urljoin(domain_base, src)
            
    return str(soup)

def fetch_articles(url=config.ZENDESK_URL, limit=config.ARTICLE_LIMIT):
    """
    Fetch articles from Zendesk Help Center API.
    Handles pagination until the limit is reached.
    """
    articles = []
    current_url = url
    
    logger.info(f"Starting to fetch articles from: {current_url}")
    
    while current_url and len(articles) < limit:
        try:
            response = requests.get(current_url, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"Error fetching articles from {current_url}: {e}")
            break
            
        page_articles = data.get("articles", [])
        if not page_articles:
            break
            
        for article in page_articles:
            # Skip drafts or articles without body content
            if article.get("draft") or not article.get("body"):
                continue
                
            articles.append(article)
            if len(articles) >= limit:
                break
                
        current_url = data.get("next_page")
        
    logger.info(f"Successfully fetched {len(articles)} articles from Zendesk.")
    return articles[:limit]

def convert_to_markdown(article):
    """
    Process a single Zendesk article dict and convert it to clean Markdown.
    Returns a dict with metadata and markdown content.
    """
    article_id = article["id"]
    title = article["name"]
    html_url = article["html_url"]
    html_body = article["body"]
    updated_at_str = article["updated_at"]
    
    # Convert updated_at string to epoch timestamp for easy delta comparison
    try:
        dt = datetime.strptime(updated_at_str, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        try:
            dt = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
        except ValueError:
            dt = datetime.utcnow()
            
    updated_timestamp = int(dt.timestamp())
    
    # Clean up relative links in HTML
    cleaned_html = clean_html_links(html_body, html_url)
    
    # Convert HTML to Markdown
    markdown_body = markdownify.markdownify(
        cleaned_html,
        heading_style="ATX",
        autolinks=True,
        wrap=False
    ).strip()
    
    # Format the final markdown document
    # We explicitly include "Article URL:" at the top so the Assistant can retrieve and cite it.
    formatted_markdown = f"# {title}\n"
    formatted_markdown += f"Article URL: {html_url}\n\n"
    formatted_markdown += markdown_body
    
    # Generate slug and filename
    title_slug = slugify(title)
    filename = f"optibot_{article_id}_{updated_timestamp}_{title_slug}.md"
    
    return {
        "id": article_id,
        "title": title,
        "url": html_url,
        "updated_at": updated_timestamp,
        "content": formatted_markdown,
        "filename": filename
    }

def scrape_all():
    """
    Orchestrator to fetch, convert, and save all articles to the local articles/ directory.
    """
    raw_articles = fetch_articles()
    processed_articles = []
    
    # Ensure local directory exists
    os.makedirs("articles", exist_ok=True)
    
    for raw in raw_articles:
        processed = convert_to_markdown(raw)
        processed_articles.append(processed)
        
        # Save to local file
        file_path = os.path.join("articles", processed["filename"])
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(processed["content"])
        logger.info(f"Saved local file: {file_path}")
        
    return processed_articles
