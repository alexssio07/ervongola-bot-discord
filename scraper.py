from scrapegraphai.graphs import SmartScraperGraph
from scrapegraphai.utils import prettify_exec_info
import asyncio

async def checkInfoFromSite():
    graph_config = {
        "llm": {
            "model": "ollama/llama3",
            "temperature": 0,
            "format": "json",  # Ollama needs the format to be specified explicitly
            "base_url": "http://localhost:11434",  # set Ollama URL
            # "base_url": "http://host.docker.internal:11434/api/generate -d",  # set Ollama URL
        },
        "embeddings": {
            "model": "ollama/nomic-embed-text",
            "base_url": "http://localhost:11434",  # set Ollama URL
            # "base_url": "http://host.docker.internal:11434/api/generate -d",  # set Ollama URL
        },
        "verbose": True,
    }

    smart_scraper_graph = SmartScraperGraph(
        prompt="Tell me the available tickets",
        # also accepts a string with the already downloaded HTML code
        source="https://www.asroma.com/it/biglietti",
        config=graph_config,
    )

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, smart_scraper_graph.run)
    
    print(result)
    return result