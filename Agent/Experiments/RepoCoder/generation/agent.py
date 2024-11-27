import os
import time
import logging
from openai import OpenAI, OpenAIError
from openai import RateLimitError

def run_agent_for_entry(prompt: str, api_key: str, retries: int = 5) -> str:
    """
    Run the agent for a specific data entry (namespace and prompt) using a specific API key.
    Implements exponential backoff for rate limits.
    
    Args:
    - prompt (str): The corresponding prompt for the function.
    - api_key (str): The API key to use for this entry.
    - retries (int): Number of retries for exponential backoff.

    Returns:
    - agent_output (str): The agent's output (completed function code).
    """
    # Set API key and base URL
    os.environ["OPENAI_API_KEY"] = api_key
    os.environ["OPENAI_BASE_URL"] = "https://api.yesapikey.com/v1"

    # Initialize OpenAI client
    client = OpenAI()

    wait_time = 1  # Initial wait time for exponential backoff
    for attempt in range(1, retries + 1):
        try:
            # Call the OpenAI model with the prompt
            response = client.chat.completions.create(
                model="gpt-4o",  # Adjust model as needed
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert python programmer. Your final output should be the fully completed function code. DO NOT include any additional descriptions in the output."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.0  # Optional: Set temperature for deterministic output
            )
            # Return the generated content
            return response.choices[0].message.content.strip()
        except RateLimitError:
            logging.warning(f"Rate limit reached for prompt. Attempt {attempt}/{retries}. Waiting for {wait_time} seconds before retrying...")
            time.sleep(wait_time)
            wait_time *= 2  # Exponential backoff
        except OpenAIError as e:
            logging.error(f"OpenAIError encountered for prompt '{prompt[:100]}': {e}")
            return ""
        except Exception as e:
            logging.error(f"Error generating completion for prompt '{prompt[:100]}': {e}")
            return ""

    logging.error(f"Failed to generate completion after {retries} attempts for prompt '{prompt[:100]}'.")
    return ""



if __name__ == "__main__":
    # Define the namespace and prompt (for example)

    target_node_label = "mistune.src.mistune.toc.add_toc_hook"
    prompt ="The code to be completed is:\n```Python\ndef add_toc_hook(md, min_level=1, max_level=3, heading_id=None):\n    def toc_hook(state):\n        headings = []\n\n        for tok in state.tokens:\n            if tok['type'] == 'heading':\n                level = tok['attrs']['level']\n                if min_level <= level <= max_level:\n                    headings.append(tok)\n\n        toc_items = []\n        for i, tok in enumerate(headings):\n            if heading_id:\n                tok['attrs']['id'] = heading_id(tok, i)\n            toc_items.append(normalize_toc_item(md, tok))\n\n        state.env['toc_items'] = toc_items\n\n    md.inline.ruler.after('heading', 'toc', toc_hook)\n```\n\nHere are some similar code snippets to help with the completion:\n\n[1] Similar code snippet (Score: 0.96):\n```Python\ndef toc_hook(md, state):\n        headings = []\n\n        for tok in state.tokens:\n            if tok['type'] == 'heading':\n                level = tok['attrs']['level']\n                if min_level <= level <= max_level:\n                    headings.append(tok)\n\n        toc_items = []\n        for i, tok in enumerate(headings):\n            tok['attrs']['id'] = heading_id(tok, i)\n            toc_items.append(normalize_toc_item(md, tok))\n\n        # save items into state\n        state.env['toc_items'] = toc_items\n```\n\n[2] Similar code snippet (Score: 0.95):\n```Python\ndef toc_hook(self, md, state):\n        sections = []\n        headings = []\n\n        for tok in state.tokens:\n            if tok['type'] == 'toc':\n                sections.append(tok)\n            elif tok['type'] == 'heading':\n                headings.append(tok)\n\n        if sections:\n            toc_items = []\n            # adding ID for each heading\n            for i, tok in enumerate(headings):\n                tok['attrs']['id'] = self.generate_heading_id(tok, i)\n                toc_items.append(normalize_toc_item(md, tok))\n\n            for sec in sections:\n                _min = sec['attrs']['min_level']\n                _max = sec['attrs']['max_level']\n                toc = [item for item in toc_items if _min <= item[0] <= _max]\n                sec['attrs']['toc'] = toc\n```\n\n[3] Similar code snippet (Score: 0.94):\n```Python\ndef add_toc_hook(md, min_level=1, max_level=3, heading_id=None):\n    \"\"\"Add a hook to save toc items into ``state.env``. This is\n    usually helpful for doc generator::\n\n        import mistune\n        from mistune.toc import add_toc_hook, render_toc_ul\n\n        md = mistune.create_markdown(...)\n        add_toc_hook(md)\n\n        html, state = md.parse(text)\n        toc_items = state.env['toc_items']\n        toc_html = render_toc_ul(toc_items)\n\n    :param md: Markdown instance\n    :param min_level: min heading level\n    :param max_level: max heading level\n    :param heading_id: a function to generate heading_id\n    \"\"\"\n    if heading_id is None:\n        def heading_id(token, index):\n            return 'toc_' + str(index + 1)\n\n    def toc_hook(md, state):\n        headings = []\n\n        for tok in state.tokens:\n            if tok['type'] == 'heading':\n                level = tok['attrs']['level']\n                if min_level <= level <= max_level:\n                    headings.append(tok)\n\n        toc_items = []\n        for i, tok in enumerate(headings):\n            tok['attrs']['id'] = heading_id(tok, i)\n            toc_items.append(normalize_toc_item(md, tok))\n\n        # save items into state\n        state.env['toc_items'] = toc_items\n\n    md.before_render_hooks.append(toc_hook)\n```\n\n[4] Similar code snippet (Score: 0.82):\n```Python\ndef parse(text):\n        md = create_markdown(escape=False)\n        add_toc_hook(md)\n        html, state = md.parse(text)\n        result = html + render_toc_ul(state.env['toc_items'])\n        return result\n```\n\n[5] Similar code snippet (Score: 0.82):\n```Python\ndef normalize_toc_item(md, token):\n    text = token['text']\n    tokens = md.inline(text, {})\n    html = md.renderer(tokens, {})\n    text = striptags(html)\n    attrs = token['attrs']\n    return attrs['level'], attrs['id'], text\n```\n\nCompleted code:"
    # Run the agent for the given entry
    apikey = "sk-1x89JfMTNXdPX1mF58B04e0c06Df4d2a90F7EcAb844a64C0"
    output = run_agent_for_entry(prompt,apikey)
    print(output)
