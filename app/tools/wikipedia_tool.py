import urllib.request
import urllib.parse
import json

def search_wikipedia(query: str) -> str:
    """
    Searches Wikipedia for a given query and returns a summary.
    Use this tool when you need general knowledge, facts, or historical information.
    """
    try:
        # First, search for the title
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&utf8=&format=json&srlimit=1"
        
        req = urllib.request.Request(search_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5.0) as response:
            search_data = json.loads(response.read().decode())
            
        search_results = search_data.get('query', {}).get('search', [])
        if not search_results:
            return f"No Wikipedia results found for '{query}'."
            
        title = search_results[0]['title']
        
        # Then, get the summary (extract)
        summary_url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&exsentences=5&exlimit=1&titles={urllib.parse.quote(title)}&explaintext=1&formatversion=2&format=json"
        req = urllib.request.Request(summary_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5.0) as response:
            summary_data = json.loads(response.read().decode())
            
        pages = summary_data.get('query', {}).get('pages', [])
        if not pages or 'extract' not in pages[0]:
            return f"Could not retrieve summary for Wikipedia page '{title}'."
            
        return f"Title: {title}\nSummary: {pages[0]['extract'].strip()}"
        
    except Exception as e:
        return f"Error searching Wikipedia: {str(e)}"
