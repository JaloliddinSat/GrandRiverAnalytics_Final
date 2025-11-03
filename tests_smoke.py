import pytest

from app import create_app
from utils.db import query_one


@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.config.update({"TESTING": True})
    with app.test_client() as client:
        yield client


def test_home(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Latest Research" in response.data


def test_blog(client):
    response = client.get("/blog")
    assert response.status_code == 200


def test_post_detail(client):
    with client.application.app_context():
        post = query_one("SELECT slug FROM posts WHERE published = 1 LIMIT 1")
        assert post is not None
        slug = post["slug"]
    response = client.get(f"/post/{slug}")
    assert response.status_code == 200


def test_team(client):
    assert client.get("/team").status_code == 200


def test_contact(client):
    assert client.get("/contact").status_code == 200


def test_rss(client):
    response = client.get("/rss.xml")
    assert response.status_code == 200
    assert b"<rss" in response.data


def test_sitemap(client):
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert b"<urlset" in response.data
