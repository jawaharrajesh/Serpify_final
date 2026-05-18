from core.scraper import (
    build_keyword_script, 
    build_redirect_script, 
    build_sitemap_script
)

def get_builder(tool_name, params):
    """
    The Universal Tool Registry.
    This function tells the Job Manager how to rebuild a spider 
    based on the tool name and the parameters stored in the database.
    
    Standard: tool_name must be lowercase_snake_case.
    """
    # Clean the input to prevent naming mismatches
    t_name = str(tool_name).lower().strip()

    # 1. KEYWORD FINDER REGISTRY
    if t_name == "keyword":
        return lambda path: build_keyword_script(
            sitemap_url=params.get("sitemap_url"),
            search_text=params.get("keyword") or params.get("search_text"),
            path_filter=params.get("path_filter", ""),
            out_json=path
        )

    # 2. REDIRECT LOOP FINDER REGISTRY
    elif t_name == "redirect":
        return lambda path: build_redirect_script(
            sitemap_url=params.get("sitemap_url"),
            path_filter=params.get("path_filter", ""),
            out_json=path
        )

    # 3. SITEMAP AUDITOR REGISTRY
    elif t_name == "sitemap":
        return lambda path: build_sitemap_script(
            sitemap_url=params.get("sitemap_url"),
            out_json=path
        )

    # Fallback if a tool is not yet registered
    return None