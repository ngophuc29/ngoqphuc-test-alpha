import io
import re
import logging
from openai import OpenAI

import config

logger = logging.getLogger(__name__)

class OpenAISyncManager:
    def __init__(self):
        config.validate_config()
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.vector_store_name = config.VECTOR_STORE_NAME
        self.assistant_id = config.OPENAI_ASSISTANT_ID
        
        # Handle version differences between openai v1 and v2 for vector_stores
        if hasattr(self.client, "vector_stores"):
            self.vector_stores_api = self.client.vector_stores
        else:
            self.vector_stores_api = self.client.beta.vector_stores


    def get_or_create_vector_store(self):
        """
        Find an existing vector store by name, or create a new one.
        """
        logger.info(f"Searching for vector store: {self.vector_store_name}")
        vector_stores = self.vector_stores_api.list()
        
        for vs in vector_stores.data:
            if vs.name == self.vector_store_name:
                logger.info(f"Found existing vector store: {vs.name} (ID: {vs.id})")
                return vs.id
                
        # If not found, create it
        logger.info(f"Vector store '{self.vector_store_name}' not found. Creating a new one...")
        vs = self.vector_stores_api.create(name=self.vector_store_name)
        logger.info(f"Created vector store: {vs.name} (ID: {vs.id})")
        return vs.id

    def get_remote_state(self):
        """
        List all files in OpenAI and identify those uploaded by OptiBot.
        Returns a dictionary mapping article_id -> {file_id, timestamp, filename}
        """
        logger.info("Retrieving remote files from OpenAI...")
        remote_state = {}
        
        # Paginate through all files in the account
        # OpenAI files.list() returns up to 10000 files by default or is paginated
        limit = 100
        after = None
        has_more = True
        
        while has_more:
            files_page = self.client.files.list(limit=limit, after=after)
            for file in files_page.data:
                # Filename pattern: optibot_{article_id}_{updated_timestamp}_{title_slug}.md
                match = re.match(r"^optibot_(\d+)_(\d+)(?:_(.+))?\.md$", file.filename)
                if match:
                    article_id = int(match.group(1))
                    timestamp = int(match.group(2))
                    remote_state[article_id] = {
                        "file_id": file.id,
                        "timestamp": timestamp,
                        "filename": file.filename
                    }
            
            has_more = files_page.has_more
            if has_more and files_page.data:
                after = files_page.data[-1].id
            else:
                break
                
        logger.info(f"Found {len(remote_state)} OptiBot files currently in OpenAI.")
        return remote_state

    def sync_articles(self, processed_articles):
        """
        Compares processed articles against remote state and performs uploads/deletes.
        """
        # Ensure we have a vector store
        vs_id = self.get_or_create_vector_store()
        
        # Get current state from OpenAI
        remote_state = self.get_remote_state()
        
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
                self._upload_and_attach(vs_id, article)
                added_count += 1
            else:
                remote_file = remote_state[article_id]
                if article["updated_at"] > remote_file["timestamp"]:
                    # Article has been updated
                    logger.info(f"Article {article_id} ('{article['title']}') has been updated. Replacing...")
                    # Delete old file
                    try:
                        self.client.files.delete(file_id=remote_file["file_id"])
                        logger.info(f"Deleted old file {remote_file['file_id']} from OpenAI.")
                    except Exception as e:
                        logger.error(f"Failed to delete old file {remote_file['file_id']}: {e}")
                        
                    # Upload new file
                    self._upload_and_attach(vs_id, article)
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
                    self.client.files.delete(file_id=remote_file["file_id"])
                    logger.info(f"Deleted orphaned file {remote_file['file_id']} from OpenAI.")
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete orphaned file {remote_file['file_id']}: {e}")

        # 3. Attach Vector Store to Assistant if ID is provided
        if self.assistant_id:
            self.attach_to_assistant(vs_id)
            
        logger.info("=== Sync Summary ===")
        logger.info(f"Added:   {added_count}")
        logger.info(f"Updated: {updated_count}")
        logger.info(f"Skipped: {skipped_count}")
        logger.info(f"Deleted: {deleted_count}")
        logger.info(f"Total active articles in Vector Store: {len(processed_articles)}")
        
        return {
            "added": added_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "deleted": deleted_count,
            "total": len(processed_articles)
        }

    def _upload_and_attach(self, vector_store_id, article):
        """
        Helper to upload a single article's markdown content to OpenAI and attach it to the vector store.
        """
        filename = article["filename"]
        content = article["content"]
        
        # Upload file to OpenAI using in-memory bytes
        file_data = io.BytesIO(content.encode("utf-8"))
        
        try:
            # Upload file
            openai_file = self.client.files.create(
                file=(filename, file_data),
                purpose="assistants"
            )
            logger.info(f"Uploaded file '{filename}' as ID: {openai_file.id}")
            
            # Attach to Vector Store
            vs_file = self.vector_stores_api.files.create(
                vector_store_id=vector_store_id,
                file_id=openai_file.id
            )
            logger.info(f"Attached file {openai_file.id} to vector store {vector_store_id}")
            return openai_file.id
        except Exception as e:
            logger.error(f"Error uploading/attaching article {article['id']}: {e}")
            raise

    def attach_to_assistant(self, vector_store_id):
        """
        Ensure the Vector Store is attached to the specified Assistant.
        """
        logger.info(f"Verifying Vector Store attachment for Assistant: {self.assistant_id}")
        try:
            assistant = self.client.beta.assistants.retrieve(assistant_id=self.assistant_id)
            
            # Check if already attached
            current_vs_ids = []
            if assistant.tool_resources and assistant.tool_resources.file_search:
                current_vs_ids = assistant.tool_resources.file_search.vector_store_ids or []
                
            if vector_store_id in current_vs_ids:
                logger.info(f"Vector Store {vector_store_id} is already attached to Assistant {self.assistant_id}.")
                return
                
            # If not attached, update the assistant
            # Merge existing vector stores if any
            new_vs_ids = list(set(current_vs_ids + [vector_store_id]))
            
            self.client.beta.assistants.update(
                assistant_id=self.assistant_id,
                tools=[{"type": "file_search"}],
                tool_resources={"file_search": {"vector_store_ids": new_vs_ids}}
            )
            logger.info(f"Successfully attached Vector Store {vector_store_id} to Assistant {self.assistant_id}.")
        except Exception as e:
            logger.error(f"Error attaching Vector Store to Assistant: {e}")
            raise
