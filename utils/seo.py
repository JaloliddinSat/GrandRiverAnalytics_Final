from __future__ import annotations

from datetime import datetime
from typing import Any


def build_meta(title: str, description: str, canonical: str, image_url: str | None = None, og_type: str = "website") -> dict[str, Any]:
    return {
        "title": title,
        "description": description,
        "canonical": canonical,
        "image_url": image_url,
        "og_type": og_type,
    }


def jsonld_org(base_url: str, name: str, description: str, logo_url: str | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "url": base_url,
        "name": name,
        "description": description,
    }
    if logo_url:
        data["logo"] = logo_url
    return data


def jsonld_website_search(base_url: str) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "url": base_url,
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{base_url}/blog?query={{search_term_string}}",
            "query-input": "required name=search_term_string",
        },
    }


def jsonld_breadcrumbs(base_url: str, crumbs: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index + 1,
                "name": label,
                "item": f"{base_url}{path}",
            }
            for index, (label, path) in enumerate(crumbs)
        ],
    }


def jsonld_blogposting(base_url: str, post: dict[str, Any], site_name: str, site_description: str) -> dict[str, Any]:
    publish_date = post.get("publish_date") or post.get("created_at")
    update_date = post.get("updated_at") or publish_date
    canonical = f"{base_url}/post/{post['slug']}"
    description = post.get("meta_description") or post.get("excerpt") or site_description
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post["title"],
        "description": description,
        "datePublished": publish_date,
        "dateModified": update_date,
        "mainEntityOfPage": canonical,
        "url": canonical,
        "author": {
            "@type": "Organization",
            "name": site_name,
        },
        "publisher": {
            "@type": "Organization",
            "name": site_name,
            "description": site_description,
        },
    }
    if post.get("cover_url"):
        data["image"] = post["cover_url"]
    tags = post.get("tags")
    if tags:
        data["keywords"] = [t.strip() for t in tags.split(",") if t.strip()]
    return data


def isoformat(dt: datetime | str | None) -> str | None:
    if isinstance(dt, datetime):
        return dt.isoformat()
    return dt
