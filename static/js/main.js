(function () {
    document.addEventListener('DOMContentLoaded', function () {
        initSearchFilter();
        initTagFilter();
        buildTableOfContents();
        initSlugSync();
        initImageFallbacks();
        ensureEmptyState();
        initLikeWidgets();
    });

    function initSearchFilter() {
        const searchInput = document.querySelector('[data-search-input]');
        if (!searchInput) return;
        const list = document.querySelector('[data-post-list]');
        const posts = Array.from(document.querySelectorAll('[data-post]'));
        searchInput.addEventListener('input', function () {
            const query = (this.value || '').toLowerCase();
            let visibleCount = 0;
            posts.forEach((post) => {
                const title = (post.getAttribute('data-post-title') || '').toLowerCase();
                const excerpt = (post.getAttribute('data-post-excerpt') || '').toLowerCase();
                const matches = title.includes(query) || excerpt.includes(query);
                post.style.display = matches ? '' : 'none';
                if (matches) visibleCount += 1;
            });
            if (list) list.setAttribute('data-visible-count', String(visibleCount));
        });
    }

    function initTagFilter() {
        const tagButtons = Array.from(document.querySelectorAll('[data-tag-filter]'));
        if (!tagButtons.length) return;
        const posts = Array.from(document.querySelectorAll('[data-post]'));
        const defaultButton = tagButtons.find((button) => button.getAttribute('data-tag-filter') === 'all');
        tagButtons.forEach((button) => {
            button.addEventListener('click', function () {
                const tag = (this.getAttribute('data-tag-filter') || '').toLowerCase();
                const wasActive = this.classList.contains('active');
                tagButtons.forEach((other) => other.classList.remove('active'));
                let activeTag = '';
                if (!wasActive) {
                    this.classList.add('active');
                    activeTag = tag;
                } else if (defaultButton) {
                    defaultButton.classList.add('active');
                } else {
                    this.classList.add('active');
                }

                posts.forEach((post) => {
                    if (!activeTag || activeTag === 'all') {
                        post.style.display = '';
                        return;
                    }
                    const tags = (post.getAttribute('data-post-tags') || '').toLowerCase();
                    const matches = tags.split(',').map((t) => t.trim()).includes(activeTag);
                    post.style.display = matches ? '' : 'none';
                });
            });
        });
    }

    function buildTableOfContents() {
        const container = document.querySelector('[data-article-content]');
        const toc = document.querySelector('[data-toc]');
        if (!container || !toc) return;

        const headings = Array.from(container.querySelectorAll('h2, h3'));
        if (!headings.length) return;

        const fragment = document.createDocumentFragment();
        headings.forEach((heading) => {
            const level = heading.tagName.toLowerCase();
            const title = heading.textContent || '';
            const id = heading.id || title.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9\-]/g, '');
            heading.id = id;
            const li = document.createElement('li');
            li.className = `toc-${level}`;
            const a = document.createElement('a');
            a.href = `#${id}`;
            a.textContent = title;
            li.appendChild(a);
            fragment.appendChild(li);
        });

        toc.appendChild(fragment);
        toc.classList.add('is-visible');
    }

    function initSlugSync() {
        const title = document.querySelector('[data-slug-title]');
        const slug = document.querySelector('[data-slug-input]');
        if (!title || !slug) return;

        const slugify = (value) =>
            (value || '')
                .toLowerCase()
                .trim()
                .replace(/[^a-z0-9\s-]/g, '')
                .replace(/[\s_-]+/g, '-')
                .replace(/^-+|-+$/g, '');

        title.addEventListener('input', () => {
            if (slug.dataset.locked === 'true') return;
            slug.value = slugify(title.value);
        });

        slug.addEventListener('input', () => {
            slug.dataset.locked = 'true';
        });
    }

    function initImageFallbacks() {
        const images = Array.from(document.querySelectorAll('img[data-img-fallback]'));
        images.forEach((image) => {
            image.addEventListener('error', () => {
                const fallback = image.getAttribute('data-img-fallback');
                if (fallback) image.src = fallback;
            });
        });
    }

    function ensureEmptyState() {
        const list = document.querySelector('[data-post-list]');
        if (!list) return;
        const posts = Array.from(document.querySelectorAll('[data-post]'));
        const empty = document.querySelector('[data-empty-state]');
        if (!empty) return;

        const update = () => {
            const anyVisible = posts.some((p) => p.style.display !== 'none');
            empty.style.display = anyVisible ? 'none' : '';
        };

        const observer = new MutationObserver(update);
        posts.forEach((post) => observer.observe(post, { attributes: true, attributeFilter: ['style'] }));
        update();
    }

    function initLikeWidgets() {
        const widgets = Array.from(document.querySelectorAll('[data-like-widget]'));
        if (!widgets.length) return;

        widgets.forEach((widget) => {
            const url = widget.getAttribute('data-like-url');
            const csrfToken = widget.getAttribute('data-csrf-token') || '';
            const button = widget.querySelector('[data-like-button]');
            const countEl = widget.querySelector('[data-like-count]');
            const labelEl = widget.querySelector('[data-like-label]');
            if (!url || !csrfToken || !button || !countEl || !labelEl) return;

            let liked = widget.getAttribute('data-liked') === '1';

            const syncUI = (nextLiked, nextCount) => {
                liked = !!nextLiked;
                widget.setAttribute('data-liked', liked ? '1' : '0');
                button.setAttribute('aria-pressed', liked ? 'true' : 'false');
                widget.classList.toggle('is-liked', liked);
                labelEl.textContent = liked ? 'Liked' : 'Like';
                if (typeof nextCount === 'number' && Number.isFinite(nextCount)) {
                    countEl.textContent = String(nextCount);
                }
            };

            // Ensure initial class matches initial state
            widget.classList.toggle('is-liked', liked);

            button.addEventListener('click', async () => {
                if (button.disabled) return;
                button.disabled = true;

                const action = liked ? 'unlike' : 'like';
                const body = new URLSearchParams();
                body.set('csrf_token', csrfToken);
                body.set('action', action);

                try {
                    const res = await fetch(url, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
                        body,
                    });

                    if (!res.ok) {
                        throw new Error('Request failed');
                    }

                    const data = await res.json();
                    syncUI(!!data.liked, Number(data.count));
                } catch (err) {
                    // If the request fails, do not change UI state.
                    console.error(err);
                } finally {
                    button.disabled = false;
                }
            });
        });
    }
})();
