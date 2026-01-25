import glob
import os

class KnowledgeBase:
    """
    A class to manage and query a knowledge base from Markdown files.
    """
    
    def __init__(self):
        self.kb_text = ""
        self.kb_files = []
    
    def load_kb_text(self, path_pattern="kb/*.md"):
        """
        Loads and concatenates text from all Markdown files matching the pattern.
        
        Args:
            path_pattern (str): Glob pattern for KB files (default: "kb/*.md").
        
        Raises:
            FileNotFoundError: If no files match the pattern.
            IOError: If a file cannot be read.
        """
        self.kb_files = sorted(glob.glob(path_pattern))
        if not self.kb_files:
            raise FileNotFoundError(f"No files found matching pattern: {path_pattern}")
        
        parts = []
        for fp in self.kb_files:
            try:
                with open(fp, encoding="utf-8") as f:
                    parts.append(f.read())
            except IOError as e:
                raise IOError(f"Error reading file {fp}: {e}")
        
        self.kb_text = "\n\n".join(parts)
    
    def _preprocess_query(self, query: str):
        """
        Preprocesses the query to extract relevant terms.
        
        Args:
            query (str): The search query.
        
        Returns:
            list: List of terms longer than 2 characters.
        """
        return [t for t in query.lower().split() if len(t) > 2]
    
    def _score_paragraphs(self, terms, paragraphs):
        """
        Scores paragraphs based on term frequency.
        
        Args:
            terms (list): List of search terms.
            paragraphs (list): List of paragraph strings.
        
        Returns:
            list: Sorted list of (score, paragraph) tuples, descending by score.
        """
        scored = []
        for p in paragraphs:
            score = sum(p.lower().count(t) for t in terms)
            if score > 0:
                scored.append((score, p))
        scored.sort(reverse=True)
        return scored
    
    def retrieve_context_keyword(self, query: str, max_chars=2200, debug=False) -> str:
        """
        Retrieves relevant context from the KB based on keyword matching.
        
        Args:
            query (str): The search query.
            max_chars (int): Maximum characters in the response (default: 2200).
            debug (bool): If True, prints the result for debugging (default: False).
        
        Returns:
            str: Concatenated relevant paragraphs, truncated to max_chars.
        
        Raises:
            ValueError: If KB text is not loaded.
        """
        if not self.kb_text:
            raise ValueError("Knowledge base text not loaded. Call load_kb_text() first.")
        
        terms = self._preprocess_query(query)
        paragraphs = [p for p in self.kb_text.split("\n\n") if p.strip()]
        scored = self._score_paragraphs(terms, paragraphs)
        
        result = "\n\n---\n\n".join(p for _, p in scored[:6])[:max_chars]
        if debug:
            print(result)
        return result

# Example usage (for testing or integration)
if __name__ == "__main__":
    kb = KnowledgeBase()
    kb.load_kb_text()
    context = kb.retrieve_context_keyword("example query", debug=True)
    print(context)