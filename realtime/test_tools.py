import asyncio
import ollama

async def test():
    client = ollama.AsyncClient()
    tools = [{
        'type': 'function',
        'function': {
            'name': 'search_web',
            'description': 'Search the internet',
            'parameters': {'type': 'object', 'properties': {'query': {'type': 'string'}}, 'required': ['query']}
        }
    }]
    
    # Try streaming
    print("Testing streaming tool call...")
    async for chunk in await client.chat(model='llama3.1', messages=[{'role': 'user', 'content': 'who is triple t?'}], tools=tools, stream=True):
        if 'tool_calls' in chunk['message']:
            print("TOOL CALL:", chunk['message']['tool_calls'])
        else:
            print("CONTENT:", chunk['message']['content'], end='')
    print("\nDone")

asyncio.run(test())
