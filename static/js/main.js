(function () {
    document.addEventListener('DOMContentLoaded', function () {
        initSearchFilter();
        initTagFilter();
        buildTableOfContents();
        initSlugSync();
        initImageFallbacks();
        ensureEmptyState();
    });

    function initSearchFilter() {
        const searchInput = document.querySelector('[data-search-input]');
        if (!searchInput) return;
        const list = document.querySelector('[data-post-list]');
        const posts = Array.from(document.querySelectorAll('[data-post]'));
        searchInput.addEventListener('input', function () {
            const term = this.value.toLowerCase();
            posts.forEach((post) => {
                const haystack = (post.getAttribute('data-title') || '').toLowerCase();
                post.style.display = haystack.includes(term) ? '' : 'none';
            });
            updateEmptyState(list, posts);
        });
    }

    function initTagFilter() {
        const tagButtons = document.querySelectorAll('[data-tag-filter]');
        if (!tagButtons.length) return;
        const list = document.querySelector('[data-post-list]');
        const posts = Array.from(document.querySelectorAll('[data-post]'));
        const defaultButton = document.querySelector('[data-tag-filter=""]');
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
                    const tags = (post.getAttribute('data-tags') || '').toLowerCase();
                    if (!activeTag || tags.includes(activeTag)) {
                        post.style.display = '';
                    } else {
                        post.style.display = 'none';
                    }
                });
                updateEmptyState(list, posts);
            });
        });
    }

    function updateEmptyState(list, posts) {
        if (!list) return;
        const emptyState = list.querySelector('[data-empty-state]');
        if (!emptyState) return;
        const hasVisible = posts.some((post) => post.style.display !== 'none');
        emptyState.hidden = hasVisible;
    }

    function ensureEmptyState() {
        const list = document.querySelector('[data-post-list]');
        if (!list) return;
        const posts = Array.from(list.querySelectorAll('[data-post]'));
        updateEmptyState(list, posts);
    }

    function buildTableOfContents() {
        const article = document.querySelector('[data-article-content]');
        const toc = document.getElementById('toc');
        if (!article || !toc) return;
        const headings = article.querySelectorAll('h2, h3');
        if (!headings.length) {
            toc.innerHTML = '<p class="muted">No sections</p>';
            return;
        }
        const list = document.createElement('ol');
        headings.forEach((heading, index) => {
            if (!heading.id) {
                heading.id = `section-${index + 1}`;
            }
            const li = document.createElement('li');
            li.className = heading.tagName.toLowerCase();
            const link = document.createElement('a');
            link.href = `#${heading.id}`;
            link.textContent = heading.textContent || `Section ${index + 1}`;
            li.appendChild(link);
            list.appendChild(li);
        });
        toc.innerHTML = '';
        toc.appendChild(list);
    }

    function initSlugSync() {
        const titleInput = document.querySelector('[data-title-input]');
        const slugInput = document.querySelector('[data-slug-input]');
        if (!titleInput || !slugInput) return;
        let userModified = slugInput.value.trim().length > 0;
        slugInput.addEventListener('input', function () {
            userModified = this.value.trim().length > 0;
        });
        titleInput.addEventListener('input', function () {
            if (userModified) return;
            const slug = this.value
                .toLowerCase()
                .trim()
                .replace(/[^a-z0-9\s-]/g, '')
                .replace(/[\s_-]+/g, '-')
                .replace(/^-+|-+$/g, '');
            slugInput.value = slug;
        });
    }

    function initImageFallbacks() {
        const images = document.querySelectorAll('[data-fallback-image]');
        images.forEach((img) => {
            const container = img.closest('[data-fallback-container]');
            if (!container) return;

            if (img.complete) {
                if (img.naturalWidth === 0) {
                    handleError(img, container);
                } else {
                    markLoaded(container);
                }
            }

            img.addEventListener('load', () => {
                markLoaded(container);
            });

            img.addEventListener('error', () => {
                handleError(img, container);
            });
        });

        function markLoaded(container) {
            container.classList.add('has-image');
            container.classList.remove('image-missing');
            container.removeAttribute('role');
            container.removeAttribute('aria-label');
            container.removeAttribute('aria-hidden');
        }

        function handleError(image, container) {
            const fallback = image.getAttribute('data-default-cover');
            if (fallback && image.src !== fallback) {
                image.src = fallback;
                return;
            }
            container.classList.add('image-missing');
            container.classList.remove('has-image');
            const label = container.getAttribute('data-placeholder-label');
            if (label) {
                container.setAttribute('role', 'img');
                container.setAttribute('aria-label', label);
            }
            container.removeAttribute('aria-hidden');
            image.remove();
        }
    }
})();
