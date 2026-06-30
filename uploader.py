import os
import re
import time
import logging
from google import genai
from google.genai import types

import config

logger = logging.getLogger(__name__)

class GeminiSyncManager:
    def __init__(self):
        config.validate_config()
        self.client = genai.Client(api_key=config.API_KEY)
        self.vector_store_name = config.VECTOR_STORE_NAME

    def get_or_create_vector_store(self):
        """
        Find an existing file search store by display_name, or create a new one.
        Returns the resource name of the store (e.g., 'fileSearchStores/12345').
        """
        logger.info(f"Searching for Gemini File Search Store: {self.vector_store_name}")
        
        try:
            # List all existing stores
            # The list method returns an iterator of stores
            stores = self.client.file_search_stores.list()
            for store in stores:
                if store.display_name == self.vector_store_name:
                    logger.info(f"Found existing store: {store.display_name} (Resource Name: {store.name})")
                    return store.name
        except Exception as e:
            logger.warning(f"Error listing stores (might be empty or new account): {e}")

        # If not found, create it
        logger.info(f"Store '{self.vector_store_name}' not found. Creating a new one...")
        try:
            store = self.client.file_search_stores.create(
                config={'display_name': self.vector_store_name}
            )
            logger.info(f"Created File Search Store: {store.display_name} (Resource Name: {store.name})")
            return store.name
        except Exception as e:
            logger.error(f"Failed to create File Search Store: {e}")
            raise

    def get_remote_state(self, store_name):
        """
        List all documents in the specified File Search Store.
        Returns a dictionary mapping article_id -> {document_name, timestamp, filename}
        """
        logger.info("Retrieving remote documents from Gemini File Search Store...")
        remote_state = {}
        
        try:
            # List documents in the store
            docs = self.client.file_search_stores.documents.list(parent=store_name)
            for doc in docs:
                # Filename pattern: optibot_{article_id}_{updated_timestamp}_{title_slug}.md
                match = re.match(r"^optibot_(\d+)_(\d+)(?:_(.+))?\.md$", doc.display_name)
                if match:
                    article_id = int(match.group(1))
                    timestamp = int(match.group(2))
                    remote_state[article_id] = {
                        "document_name": doc.name,  # Resource name used for deletion
                        "timestamp": timestamp,
                        "filename": doc.display_name
                    }
        except Exception as e:
            logger.error(f"Error retrieving remote state: {e}")
            
        logger.info(f"Found {len(remote_state)} OptiBot documents currently in Gemini.")
        return remote_state

    def sync_articles(self, processed_articles):
        """
        Compares processed articles against remote state and performs uploads/deletes.
        """
        # Ensure we have a file search store
        store_name = self.get_or_create_vector_store()
        
        # Get current state from Gemini
        remote_state = self.get_remote_state(store_name)
        
        added_count = 0
        updated_count = 0
        skipped_count = 0
        deleted_count = 0
        
        active_article_ids = set()
        
        # 1. Upload new/updated articles
        for article in processed_articles:
            article_id = article["id"]
            active_article_ids.add(article_id)
            
            if article_id not in remote_state:
                # Brand new article
                logger.info(f"Article {article_id} ('{article['title']}') is new. Uploading...")
                self._upload_to_store(store_name, article)
                added_count += 1
            else:
                remote_file = remote_state[article_id]
                if article["updated_at"] > remote_file["timestamp"]:
                    # Article has been updated
                    logger.info(f"Article {article_id} ('{article['title']}') has been updated. Replacing...")
                    # Delete old document from store
                    try:
                        self.client.file_search_stores.documents.delete(name=remote_file["document_name"])
                        logger.info(f"Deleted old document {remote_file['document_name']} from Gemini.")
                    except Exception as e:
                        logger.error(f"Failed to delete old document {remote_file['document_name']}: {e}")
                        
                    # Upload new file
                    self._upload_to_store(store_name, article)
                    updated_count += 1
                else:
                    # No changes
                    logger.debug(f"Article {article_id} ('{article['title']}') is unchanged. Skipping.")
                    skipped_count += 1
                    
        # 2. Clean up orphaned articles (deleted from Zendesk or fell out of the top N)
        for article_id, remote_file in remote_state.items():
            if article_id not in active_article_ids:
                logger.info(f"Article {article_id} ('{remote_file['filename']}') no longer active. Deleting...")
                try:
                    self.client.file_search_stores.documents.delete(name=remote_file["document_name"])
                    logger.info(f"Deleted orphaned document {remote_file['document_name']} from Gemini.")
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete orphaned document {remote_file['document_name']}: {e}")
            
        logger.info("=== Sync Summary ===")
        logger.info(f"Added:   {added_count}")
        logger.info(f"Updated: {updated_count}")
        logger.info(f"Skipped: {skipped_count}")
        logger.info(f"Deleted: {deleted_count}")
        logger.info(f"Total active articles in File Search Store: {len(processed_articles)}")
        
        return {
            "added": added_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "deleted": deleted_count,
            "total": len(processed_articles)
        }

    def _upload_to_store(self, store_name, article):
        """
        Helper to upload a single article's local markdown file to the Gemini File Search Store.
        """
        filename = article["filename"]
        file_path = os.path.join("articles", filename)
        
        try:
            # Upload and index file using Gemini File Search API
            # This is an asynchronous operation
            operation = self.client.file_search_stores.upload_to_file_search_store(
                file=file_path,
                file_search_store_name=store_name,
                config={'display_name': filename, 'mime_type': 'text/markdown'}
            )
            
            logger.info(f"Uploading '{filename}' to Gemini (Operation: {operation.name})...")
            
            # Poll the operation until it's done
            wait_time = 1
            while not operation.done:
                time.sleep(wait_time)
                operation = self.client.operations.get(operation)
                # Cap polling wait time at 5 seconds
                wait_time = min(wait_time + 1, 5)
                
            logger.info(f"Successfully uploaded and indexed '{filename}' in Gemini.")
        except Exception as e:
            logger.error(f"Error uploading article {article['id']} to Gemini: {e}")
            raise
