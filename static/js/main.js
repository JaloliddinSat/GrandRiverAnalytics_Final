(function () {
    document.addEventListener('DOMContentLoaded', function () {
        initSearchFilter();
        initTagFilter();
        buildTableOfContents();
        initSlugSync();
    });

    function initSearchFilter() {
        const searchInput = document.querySelector('[data-search-input]');
        if (!searchInput) return;
        const posts = Array.from(document.querySelectorAll('[data-post]'));
        searchInput.addEventListener('input', function () {
            const term = this.value.toLowerCase();
            posts.forEach((post) => {
                const haystack = (post.getAttribute('data-title') || '').toLowerCase();
                post.style.display = haystack.includes(term) ? '' : 'none';
            });
        });
    }

    function initTagFilter() {
        const tagButtons = document.querySelectorAll('[data-tag-filter]');
        if (!tagButtons.length) return;
        const posts = Array.from(document.querySelectorAll('[data-post]'));
        tagButtons.forEach((button) => {
            button.addEventListener('click', function () {
                const tag = this.getAttribute('data-tag-filter');
                const isActive = this.classList.toggle('active');
                tagButtons.forEach((other) => {
                    if (other !== this) other.classList.remove('active');
                });
                posts.forEach((post) => {
                    const tags = (post.getAttribute('data-tags') || '').toLowerCase();
                    if (!isActive || tags.includes(tag.toLowerCase())) {
                        post.style.display = '';
                    } else {
                        post.style.display = 'none';
                    }
                });
            });
        });
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
})();
