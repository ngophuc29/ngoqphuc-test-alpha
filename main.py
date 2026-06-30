import sys
import logging
import scraper
from uploader import GeminiSyncManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("optibot_sync")

def main():
    logger.info("Starting OptiBot Mini-Clone Sync Job (Gemini)...")
    
    try:
        # Step 1: Scrape articles from Zendesk and convert to Markdown
        logger.info("Step 1: Scraping articles from Zendesk...")
        processed_articles = scraper.scrape_all()
        
        if not processed_articles:
            logger.warning("No articles were scraped. Exiting sync job.")
            sys.exit(0)
            
        logger.info(f"Scraped, processed, and saved {len(processed_articles)} articles locally.")
        
        # Step 2: Sync with Gemini File Search Store
        logger.info("Step 2: Syncing with Gemini File Search Store...")
        sync_manager = GeminiSyncManager()
        summary = sync_manager.sync_articles(processed_articles)
        
        logger.info("Sync job completed successfully!")
        logger.info(
            f"Summary - Added: {summary['added']}, Updated: {summary['updated']}, "
            f"Skipped: {summary['skipped']}, Deleted: {summary['deleted']}, Total: {summary['total']}"
        )
        
    except Exception as e:
        logger.exception(f"Sync job failed with an error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
