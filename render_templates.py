"""
AutoRide Sniper - Jinja2 Template Compiler
Compiles modular Jinja2 templates (extending base.html) into static HTML files
for both backend/static/showcase/ and showcase/.
"""

import os
import json
from jinja2 import Environment, FileSystemLoader

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BACKEND_DIR, "templates")
STATIC_SHOWCASE_DIR = os.path.join(BACKEND_DIR, "static", "showcase")
ROOT_SHOWCASE_DIR = os.path.abspath(os.path.join(BACKEND_DIR, "..", "showcase"))
LATEST_RELEASE_FILE = os.path.abspath(os.path.join(BACKEND_DIR, "..", "app_releases", "latest_release.json"))
VERSION_FILE = os.path.abspath(os.path.join(BACKEND_DIR, "..", "mobile", "version.json"))

def get_app_version():
    try:
        if os.path.exists(LATEST_RELEASE_FILE):
            with open(LATEST_RELEASE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                v = data.get("latest_version")
                if v:
                    return v if str(v).startswith("v") else f"v{v}"
        if os.path.exists(VERSION_FILE):
            with open(VERSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                v = data.get("versionName")
                if v:
                    return v if str(v).startswith("v") else f"v{v}"
    except Exception:
        pass
    return "v1.0.5"

def render_all_templates():
    if not os.path.exists(TEMPLATES_DIR):
        print(f"[Template Compiler] Error: {TEMPLATES_DIR} does not exist.")
        return False

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=False)
    app_version = get_app_version()
    context = {"app_version": app_version}

    pages = [
        "index.html",
        "pricing.html",
        "privacy.html",
        "terms.html",
        "refund.html",
        "contact.html"
    ]

    os.makedirs(STATIC_SHOWCASE_DIR, exist_ok=True)
    os.makedirs(ROOT_SHOWCASE_DIR, exist_ok=True)

    print(f"[Template Compiler] Compiling Jinja2 templates with version={app_version}...")

    for page in pages:
        template_file = os.path.join(TEMPLATES_DIR, page)
        if not os.path.exists(template_file):
            print(f"[Template Compiler] Warning: {page} not found in templates directory.")
            continue

        template = env.get_template(page)
        rendered_html = template.render(**context)

        # Output to backend/static/showcase/
        out_path_1 = os.path.join(STATIC_SHOWCASE_DIR, page)
        with open(out_path_1, "w", encoding="utf-8") as f:
            f.write(rendered_html)

        # Output to showcase/
        out_path_2 = os.path.join(ROOT_SHOWCASE_DIR, page)
        with open(out_path_2, "w", encoding="utf-8") as f:
            f.write(rendered_html)

        print(f"  [OK] Compiled {page} -> backend/static/showcase/ & showcase/")

    print("[Template Compiler] Done! All pages compiled with base layout consistency.")
    return True

if __name__ == "__main__":
    render_all_templates()
