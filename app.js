// Academic News Feed Application Logic

document.addEventListener('DOMContentLoaded', () => {
    // State management
    let allArticles = [];
    let currentCategory = 'all';
    let showFavoritesOnly = false;
    let favorites = JSON.parse(localStorage.getItem('psych_news_favorites')) || [];
    
    // Pagination / Lazy rendering state
    const ITEMS_PER_PAGE = 12; // Hero (1) + Grid (11) = 12 initial. Load 12 more each click.
    let visibleCount = 11;

    // DOM Elements
    const tabButtons = document.querySelectorAll('.tab-btn');
    const newsGrid = document.getElementById('news-grid');
    const featuredSection = document.getElementById('featured-section');
    const toggleFavoritesBtn = document.getElementById('toggle-favorites');
    const shareFavoritesBtn = document.getElementById('share-favorites');
    const updateFeedBtn = document.getElementById('update-feed-btn');
    const syncSettingsPanel = document.getElementById('sync-settings-panel');
    const currentSyncKeyEl = document.getElementById('current-sync-key');
    const changeSyncKeyBtn = document.getElementById('change-sync-key-btn');

    // Supabase Configuration
    const supabaseUrl = 'https://ubinbmcxxpoqkhcxhjkj.supabase.co';
    const supabaseKey = 'sb_publishable_ir_3nxQ6RfaEb_-goiREAg_tzyVn722';
    const supabaseClient = (typeof supabase !== 'undefined') ? supabase.createClient(supabaseUrl, supabaseKey) : (typeof window.supabase !== 'undefined' ? window.supabase.createClient(supabaseUrl, supabaseKey) : null);
    const loadMoreBtn = document.getElementById('load-more-btn');
    const loadMoreContainer = document.querySelector('.load-more-container');
    const syncStatusText = document.getElementById('sync-status');
    const statusDot = document.querySelector('.status-dot');
    
    // Detail Panel Elements
    const detailPanel = document.getElementById('detail-panel');
    const detailBackdrop = document.getElementById('detail-backdrop');
    const closeDetailBtn = document.getElementById('close-detail');
    const detailImg = document.getElementById('detail-img');
    const detailCategory = document.getElementById('detail-category');
    const detailTitle = document.getElementById('detail-title');
    const detailOrigTitle = document.getElementById('detail-orig-title');
    const detailSource = document.getElementById('detail-source');
    const detailDate = document.getElementById('detail-date');
    const detailMethodology = document.getElementById('detail-methodology');
    const detailSummary = document.getElementById('detail-summary');
    const detailClinical = document.getElementById('detail-clinical');
    const detailResearch = document.getElementById('detail-research');
    const detailPubmedLink = document.getElementById('detail-pubmed-link');
    const detailFavBtn = document.getElementById('detail-fav-btn');

    // Category classes mapping
    const categoryClasses = {
        'Coercion & Ethics': 'badge-coercion',
        'Psychiatric Nursing': 'badge-nursing',
        'General Medical Science': 'badge-general',
        'Research Methods': 'badge-methods'
    };

    // Category translation helper
    const categoryNamesJA = {
        'Coercion & Ethics': '強制と倫理',
        'Psychiatric Nursing': '精神科看護',
        'General Medical Science': '医学・科学一般',
        'Research Methods': '研究方法論'
    };

    // Cloud sync helper functions
    async function syncFavoritesToCloud() {
        const syncKey = localStorage.getItem('psych_news_sync_key');
        if (!syncKey || !supabaseClient) return;
        try {
            const { error } = await supabaseClient
                .from('user_favorites')
                .upsert({ sync_key: syncKey, favorite_ids: favorites, updated_at: new Date() });
            if (error) throw error;
            console.log('Cloud sync successful');
        } catch (err) {
            console.error('Cloud sync failed:', err);
        }
    }

    async function loadFavoritesFromCloud(syncKey) {
        if (!syncKey || !supabaseClient) return;
        try {
            const { data, error } = await supabaseClient
                .from('user_favorites')
                .select('favorite_ids')
                .eq('sync_key', syncKey)
                .maybeSingle();
            if (error) throw error;
            if (data && data.favorite_ids) {
                favorites = data.favorite_ids;
                localStorage.setItem('psych_news_favorites', JSON.stringify(favorites));
                updateFavoritesBtnStyle();
                console.log('Cloud favorites loaded:', favorites);
            }
        } catch (err) {
            console.error('Failed to load cloud favorites:', err);
        }
    }

    function updateSyncPanelUI() {
        const syncKey = localStorage.getItem('psych_news_sync_key');
        if (syncKey && showFavoritesOnly) {
            syncSettingsPanel.style.display = 'inline-flex';
            currentSyncKeyEl.textContent = syncKey;
        } else {
            syncSettingsPanel.style.display = 'none';
        }
    }

    // Helper to parse PubMed style date strings to Date object for sorting
    const monthMap = {
        'jan': 0, 'feb': 1, 'mar': 2, 'apr': 3, 'may': 4, 'jun': 5,
        'jul': 6, 'aug': 7, 'sep': 8, 'oct': 9, 'nov': 10, 'dec': 11
    };

    function parseArticleDate(dateStr) {
        if (!dateStr) return new Date(0);
        // Handle Japanese date strings if any
        if (dateStr.includes('年')) {
            const match = dateStr.match(/(\d+)年(\d+)月?(\d+)?日?/);
            if (match) {
                const y = parseInt(match[1], 10);
                const m = parseInt(match[2], 10) - 1;
                const d = match[3] ? parseInt(match[3], 10) : 1;
                return new Date(y, m, d);
            }
        }
        const parts = dateStr.trim().split(/\s+/);
        let year = 2026;
        let month = 0;
        let day = 1;
        
        if (parts.length > 0) {
            const y = parseInt(parts[0], 10);
            if (!isNaN(y)) year = y;
        }
        if (parts.length > 1) {
            const mStr = parts[1].toLowerCase().substring(0, 3);
            if (monthMap[mStr] !== undefined) {
                month = monthMap[mStr];
            }
        }
        if (parts.length > 2) {
            const d = parseInt(parts[2], 10);
            if (!isNaN(d)) day = d;
        }
        return new Date(year, month, day);
    }

    // Initialize application by fetching JSON data
    async function init() {
        try {
            // Add timestamp query to bypass cache
            const response = await fetch('src/data/articles.json?t=' + Date.now());
            if (!response.ok) {
                throw new Error('Failed to fetch articles database');
            }
            allArticles = await response.json();
            
            // Sort articles by publication date descending (newest first)
            // (Commented out so newly added or backfilled past articles show up at the top in database order)
            // allArticles.sort((a, b) => parseArticleDate(b.published) - parseArticleDate(a.published));
            
            // Handle URL Sync Key for automated setup
            const urlParams = new URLSearchParams(window.location.search);
            const syncKeyParam = urlParams.get('sync_key');
            if (syncKeyParam) {
                localStorage.setItem('psych_news_sync_key', syncKeyParam);
                await loadFavoritesFromCloud(syncKeyParam);
                showToast(`合言葉「${syncKeyParam}」で自動同期を開始しました！`);
                window.history.replaceState({}, document.title, window.location.pathname);
            } else {
                // Pull latest from cloud if sync key already exists locally
                const existingSyncKey = localStorage.getItem('psych_news_sync_key');
                if (existingSyncKey) {
                    await loadFavoritesFromCloud(existingSyncKey);
                }
            }
            
            renderFeed();
            updateSyncStatus();
        } catch (error) {
            console.error('Initialization error:', error);
            newsGrid.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                    <p>データを読み込めませんでした。現在データベースを作成中か、一時的なエラーの可能性があります。</p>
                </div>
            `;
            featuredSection.innerHTML = '';
            loadMoreContainer.style.display = 'none';
        }
    }

    // Update synchronization status text
    function updateSyncStatus() {
        if (syncStatusText) {
            const now = new Date();
            const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
            syncStatusText.textContent = `同期済み (${timeStr})`;
        }
    }

    // Render the feed (featured article + grid cards with pagination)
    function renderFeed() {
        // Filter articles based on state (category + favorites filter)
        const filtered = allArticles.filter(article => {
            const matchesCategory = currentCategory === 'all' || article.category === currentCategory;
            const matchesFavorites = !showFavoritesOnly || favorites.includes(article.id);
            return matchesCategory && matchesFavorites;
        });

        // Clear existing feed
        featuredSection.innerHTML = '';
        newsGrid.innerHTML = '';

        if (filtered.length === 0) {
            newsGrid.innerHTML = `
                <div class="empty-state">
                    <i class="fa-regular fa-folder-open"></i>
                    <p>${showFavoritesOnly ? 'お気に入りに登録されている論文がありません。' : '該当する論文ニュースがありません。'}</p>
                </div>
            `;
            loadMoreContainer.style.display = 'none';
            return;
        }

        // Render Hero / Featured (Only if we aren't showing favorites-only, or if there is at least one favorite)
        const featuredArticle = filtered[0];
        const gridArticles = filtered.slice(1);

        renderHeroCard(featuredArticle);

        // Slice grid articles according to pagination (visibleCount)
        const visibleGridArticles = gridArticles.slice(0, visibleCount);

        // Render remaining in the grid
        if (visibleGridArticles.length > 0) {
            visibleGridArticles.forEach(article => {
                const card = createNewsCard(article);
                newsGrid.appendChild(card);
            });
        } else if (filtered.length === 1) {
            newsGrid.innerHTML = `
                <div class="empty-state" style="padding: 2rem 0;">
                    <p>他に関連する論文はありません。</p>
                </div>
            `;
        }

        // Show or hide the "Load More" button
        if (gridArticles.length > visibleGridArticles.length) {
            loadMoreContainer.style.display = 'flex';
        } else {
            loadMoreContainer.style.display = 'none';
        }
    }

    // Helper to get fallback gradient based on category
    function getFallbackGradient(category) {
        switch(category) {
            case 'Coercion & Ethics':
                return 'linear-gradient(135deg, #1e1b4b, #4c1d95)';
            case 'Psychiatric Nursing':
                return 'linear-gradient(135deg, #064e3b, #047857)';
            case 'General Medical Science':
                return 'linear-gradient(135deg, #0c4a6e, #0369a1)';
            case 'Research Methods':
                return 'linear-gradient(135deg, #581c87, #7e22ce)';
            default:
                return 'linear-gradient(135deg, #0f172a, #1e293b)';
        }
    }

    // Render the featured hero card
    function renderHeroCard(article) {
        const isFav = favorites.includes(article.id);
        const badgeClass = categoryClasses[article.category] || '';
        const categoryName = categoryNamesJA[article.category] || article.category;
        
        const heroElement = document.createElement('div');
        heroElement.className = 'hero-card';
        
        const bgStyle = article.imageUrl 
            ? `background-image: url('${article.imageUrl}')` 
            : `background: ${getFallbackGradient(article.category)}`;

        heroElement.innerHTML = `
            <div class="hero-img" style="${bgStyle}"></div>
            <div class="hero-overlay"></div>
            <div class="hero-content">
                <span class="hero-badge ${badgeClass}">${categoryName}</span>
                <h2 class="hero-title">${article.title}</h2>
                <p class="hero-desc">${article.summary}</p>
                <div class="hero-meta">
                    <span><i class="fa-solid fa-book-open"></i> ${article.source}</span>
                    <span><i class="fa-regular fa-calendar"></i> ${article.published}</span>
                </div>
            </div>
        `;

        heroElement.addEventListener('click', () => {
            openDetailPanel(article);
        });

        featuredSection.appendChild(heroElement);
    }

    // Create a news card element
    function createNewsCard(article) {
        const isFav = favorites.includes(article.id);
        const badgeClass = categoryClasses[article.category] || '';
        const categoryName = categoryNamesJA[article.category] || article.category;

        const card = document.createElement('div');
        card.className = 'news-card';
        
        const imgStyle = article.imageUrl 
            ? `background-image: url('${article.imageUrl}')` 
            : `background: ${getFallbackGradient(article.category)}`;

        card.innerHTML = `
            <div class="card-img-wrapper">
                <div class="card-img" style="${imgStyle}"></div>
                <span class="card-badge ${badgeClass}">${categoryName}</span>
            </div>
            <div class="card-body">
                <div class="card-source-row">
                    <span class="card-source">${article.source}</span>
                    <span class="card-date">${article.published}</span>
                </div>
                <h3 class="card-title">${article.title}</h3>
                <p class="card-desc">${article.summary}</p>
                <div class="card-footer">
                    <span class="card-method-badge" title="手法: ${article.methodology}">
                        <i class="fa-solid fa-flask"></i> ${article.methodology}
                    </span>
                    <button class="card-fav-btn ${isFav ? 'is-fav' : ''}" data-id="${article.id}">
                        <i class="${isFav ? 'fa-solid' : 'fa-regular'} fa-bookmark"></i>
                    </button>
                </div>
            </div>
        `;

        const favBtn = card.querySelector('.card-fav-btn');
        favBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleFavorite(article.id);
            const activeIsFav = favorites.includes(article.id);
            favBtn.classList.toggle('is-fav', activeIsFav);
            const icon = favBtn.querySelector('i');
            icon.className = activeIsFav ? 'fa-solid fa-bookmark' : 'fa-regular fa-bookmark';
            
            if (showFavoritesOnly) {
                renderFeed();
            }
        });

        card.addEventListener('click', () => {
            openDetailPanel(article);
        });

        return card;
    }

    // Toggle favorite state of an article ID
    function toggleFavorite(id) {
        const index = favorites.indexOf(id);
        if (index === -1) {
            favorites.push(id);
        } else {
            favorites.splice(index, 1);
        }
        localStorage.setItem('psych_news_favorites', JSON.stringify(favorites));
        updateFavoritesBtnStyle();
        syncFavoritesToCloud(); // Sync to Supabase
    }

    function updateFavoritesBtnStyle() {
        if (favorites.length > 0) {
            toggleFavoritesBtn.querySelector('i').className = 'fa-solid fa-bookmark';
            toggleFavoritesBtn.style.color = 'var(--accent-amber)';
        } else {
            toggleFavoritesBtn.querySelector('i').className = 'fa-regular fa-bookmark';
            toggleFavoritesBtn.style.color = 'var(--text-primary)';
        }
    }

    // Open detail slide-over panel
    function openDetailPanel(article) {
        const isFav = favorites.includes(article.id);
        const badgeClass = categoryClasses[article.category] || '';
        const categoryName = categoryNamesJA[article.category] || article.category;

        if (article.imageUrl) {
            detailImg.style.backgroundImage = `url('${article.imageUrl}')`;
            detailImg.style.background = '';
        } else {
            detailImg.style.backgroundImage = '';
            detailImg.style.background = getFallbackGradient(article.category);
        }
        
        detailCategory.textContent = categoryName;
        detailCategory.className = `detail-tag ${badgeClass}`;
        
        detailTitle.textContent = article.title;
        detailOrigTitle.textContent = article.originalTitle;
        detailSource.innerHTML = `<i class="fa-solid fa-book-open"></i> ${article.source}`;
        detailDate.innerHTML = `<i class="fa-regular fa-calendar"></i> ${article.published}`;
        detailMethodology.textContent = article.methodology;
        
        detailSummary.textContent = article.summary;
        detailClinical.textContent = article.clinicalImplication || '本研究の臨床的意義はまだ評価されていません。';
        detailResearch.textContent = article.researchImplication || '本研究の研究への意義はまだ評価されていません。';
        
        detailPubmedLink.href = article.url || '#';
        
        updateModalFavBtn(isFav, article.id);

        // Bind click listener to modal fav button using onclick to safely overwrite previous listener
        const favBtn = document.getElementById('detail-fav-btn');
        favBtn.onclick = () => {
            toggleFavorite(article.id);
            const activeIsFav = favorites.includes(article.id);
            updateModalFavBtn(activeIsFav, article.id);
            renderFeed(); // Re-render main feed to synchronize states
        };
        
        detailPanel.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    function updateModalFavBtn(isFav, id) {
        const btn = document.getElementById('detail-fav-btn');
        if (isFav) {
            btn.classList.add('is-fav');
            btn.innerHTML = `<i class="fa-solid fa-bookmark"></i> お気に入りから削除`;
        } else {
            btn.classList.remove('is-fav');
            btn.innerHTML = `<i class="fa-regular fa-bookmark"></i> お気に入りに保存`;
        }
    }

    // Close detail slide-over panel
    function closeDetailPanel() {
        detailPanel.classList.remove('active');
        document.body.style.overflow = '';
    }

    // Event Listeners for Tabs
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            tabButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            currentCategory = btn.getAttribute('data-category');
            // Reset pagination on category change
            visibleCount = 4;
            renderFeed();
        });
    });

    // Event Listener for Favorites Filter Button
    toggleFavoritesBtn.addEventListener('click', () => {
        showFavoritesOnly = !showFavoritesOnly;
        toggleFavoritesBtn.classList.toggle('active', showFavoritesOnly);
        
        const gridTitle = document.getElementById('grid-title');
        if (showFavoritesOnly) {
            gridTitle.textContent = 'お気に入りの論文';
            shareFavoritesBtn.style.display = 'inline-flex';
        } else {
            gridTitle.textContent = '最新の論文ニュース';
            shareFavoritesBtn.style.display = 'none';
        }
        updateSyncPanelUI();
        
        // Reset pagination on mode change
        visibleCount = 11;
        renderFeed();
    });

    // Event Listener for "Share Favorites" Sync Button
    shareFavoritesBtn.addEventListener('click', async () => {
        let syncKey = localStorage.getItem('psych_news_sync_key');
        if (!syncKey) {
            // Generate a random-like proposed key
            const proposedKey = 'pn-' + Math.random().toString(36).substring(2, 8);
            const key = prompt("他端末と自動同期するための「合言葉」を入力してください。\n(英数字でご自由に入力してください。未入力の場合は自動生成します)", proposedKey);
            if (key === null) return; // Cancelled
            syncKey = key.trim() || proposedKey;
            localStorage.setItem('psych_news_sync_key', syncKey);
            updateSyncPanelUI();
            // Initial upload
            await syncFavoritesToCloud();
        }
        
        const shareUrl = `${window.location.origin}${window.location.pathname}?sync_key=${syncKey}`;
        navigator.clipboard.writeText(shareUrl).then(() => {
            showToast('自動同期用のリンクをコピーしました！別のアカウントやスマホでこのリンクを一度開いてください。');
        }).catch(err => {
            console.error('Failed to copy URL:', err);
            showToast('URL of sync failed to copy.');
        });
    });

    // Event Listener for "Change Sync Key" Button
    changeSyncKeyBtn.addEventListener('click', async () => {
        const currentKey = localStorage.getItem('psych_news_sync_key') || '';
        const newKey = prompt("新しい自動同期用の「合言葉」を入力してください。\n(別端末で設定した合言葉を入力すると、その端末のお気に入りと自動同期されます。空欄にすると同期を解除します)", currentKey);
        if (newKey === null) return; // Cancelled
        const trimmedKey = newKey.trim();
        if (!trimmedKey) {
            localStorage.removeItem('psych_news_sync_key');
            updateSyncPanelUI();
            showToast('自動同期を解除しました。');
        } else {
            localStorage.setItem('psych_news_sync_key', trimmedKey);
            updateSyncPanelUI();
            showToast(`合言葉を「${trimmedKey}」に変更しました。データを読み込みます...`);
            await loadFavoritesFromCloud(trimmedKey);
            renderFeed();
        }
    });

    // Event Listener for "Load More" Pagination Button
    loadMoreBtn.addEventListener('click', () => {
        visibleCount += ITEMS_PER_PAGE;
        renderFeed();
    });

    // Infinite Scroll setup (SmartNews-like auto load)
    if ('IntersectionObserver' in window && loadMoreBtn) {
        const observer = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting) {
                if (loadMoreContainer.style.display !== 'none' && !updateFeedBtn.disabled) {
                    visibleCount += ITEMS_PER_PAGE;
                    renderFeed();
                }
            }
        }, {
            rootMargin: '200px',
            threshold: 0
        });
        observer.observe(loadMoreBtn);
    }

    // Guide Modal Elements for Production Update
    const updateGuideModal = document.getElementById('update-guide-modal');
    const updateGuideBackdrop = document.getElementById('update-guide-backdrop');
    const closeUpdateGuideBtn = document.getElementById('close-update-guide');
    const btnCloseGuide = document.getElementById('btn-close-guide');

    function openUpdateGuide() {
        if (updateGuideModal) {
            updateGuideModal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    }

    function closeUpdateGuide() {
        if (updateGuideModal) {
            updateGuideModal.classList.remove('active');
            document.body.style.overflow = '';
        }
    }

    if (closeUpdateGuideBtn) closeUpdateGuideBtn.addEventListener('click', closeUpdateGuide);
    if (updateGuideBackdrop) updateGuideBackdrop.addEventListener('click', closeUpdateGuide);
    if (btnCloseGuide) btnCloseGuide.addEventListener('click', closeUpdateGuide);

    // Event Listener for "Fetch Latest" API Update Button
    updateFeedBtn.addEventListener('click', async () => {
        const isProduction = window.location.hostname.endsWith('github.io');
        
        if (isProduction) {
            openUpdateGuide();
            return;
        }

        const icon = updateFeedBtn.querySelector('i');
        icon.classList.add('spin');
        updateFeedBtn.disabled = true;

        // Set status to syncing (orange)
        statusDot.className = 'status-dot orange';
        statusDot.style.boxShadow = '0 0 8px var(--accent-amber)';
        syncStatusText.textContent = '最新情報を検索中...';

        try {
            const response = await fetch('/api/update', {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error('API server returned error code');
            }

            const result = await response.json();
            console.log("Database update successful:", result);

            // Re-fetch the newly generated articles database
            const dataResponse = await fetch('src/data/articles.json?t=' + Date.now());
            if (dataResponse.ok) {
                allArticles = await dataResponse.json();
            }

            // Reset pagination and re-render
            visibleCount = 4;
            renderFeed();

            // Set status to synced (green)
            statusDot.className = 'status-dot green';
            statusDot.style.boxShadow = '0 0 8px var(--accent-green)';
            updateSyncStatus();

            // Show outcome toast
            if (result.output && result.output.includes("No new articles found")) {
                showToast("新着論文はありませんでした。データベースは最新です。");
            } else {
                const match = result.output ? result.output.match(/Added (\d+) articles/) : null;
                const count = match ? match[1] : "新着";
                showToast(`更新完了！最新論文を ${count} 件追加しました。`);
            }

        } catch (error) {
            console.error('Update failed:', error);
            showToast('更新失敗。APIサーバーの接続を確認してください。');
            
            statusDot.className = 'status-dot green';
            statusDot.style.boxShadow = '0 0 8px var(--accent-green)';
            updateSyncStatus();
        } finally {
            icon.classList.remove('spin');
            updateFeedBtn.disabled = false;
        }
    });

    // Helper to display toast notifications
    function showToast(message) {
        const existingToast = document.querySelector('.toast-notification');
        if (existingToast) {
            existingToast.remove();
        }

        const toast = document.createElement('div');
        toast.className = 'toast-notification';
        toast.textContent = message;
        document.body.appendChild(toast);

        // Animate in
        setTimeout(() => {
            toast.classList.add('show');
        }, 50);

        // Hide and remove after 3.5s
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                toast.remove();
            }, 300);
        }, 3500);
    }

    // Close panel triggers
    closeDetailBtn.addEventListener('click', closeDetailPanel);
    detailBackdrop.addEventListener('click', closeDetailPanel);
    
    // Keyboard close (ESC)
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (detailPanel.classList.contains('active')) {
                closeDetailPanel();
            }
            if (updateGuideModal && updateGuideModal.classList.contains('active')) {
                closeUpdateGuide();
            }
        }
    });

    // Initial load
    updateFavoritesBtnStyle();
    init();
});
